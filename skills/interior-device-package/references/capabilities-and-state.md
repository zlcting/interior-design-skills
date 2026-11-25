# 能力、状态与 SDK 配方

创建设备时把下表随功能说明交付。操作目标、当前反馈和模型效果是不同字段；全部必须能追溯到合同中的完整能力引用。

| 设备示例 | 操作 | 当前可读状态 | 可见反馈 |
|---|---|---|---|
| 空调 | 开关、冷/暖模式 | 运行状态、实际模式 | 冷蓝/暖橙预制气流；停止隐藏 |
| 机器人 | 清扫、暂停、回座 | cleaningState、isDocked、chargingStatus | 外出隐藏机身，基座不动；确认归座后出现 |
| 窗帘 | 目标开度、停止 | position、movementState | 开合、停止保留位置 |
| 灯 | 开关、亮度 | power、brightness | 发光面与实际灯光同步 |
| 净化器/无雾加湿器 | 开关、档位 | 运行状态、模式 | 气流或无雾运行提示 |
| 冰箱/插座/门锁 | 任务确认的操作 | 门开/电源/童锁/故障/锁定等 | 模型状态指示；不凭空增加门扇或执手机械动画 |

这些字段名是配方，不是所有商品必有的能力。传感器可只有只读状态；具体枚举、采样、尺寸及模式需要产品依据。用户明确要求演示时才编写模拟变化，并标明`simulation`；真实反馈适配未接通时不得宣称已实现。

## 源包的三个部分

1. `device-contract.json`：标准能力、类型、权限、初值、控件、效果及命令模拟。只读属性用`read`，无参数命令用`value.type=null`和execute的`value:null`。
2. `device-state.json`：源包的状态说明，不是SDK新Schema字段。`entries.stateDescription`指向它，新交互包声明`requiredFeatures: [{"id":"device.state-simulation","version":1}]`。
3. `behavior.template.json`：需要派生状态、连续动作或归座等过程时提供。`entries.behavior`指向它；装配器为每个实例填入deviceId并编译为标准`home3d.device-program.v1`，不会执行包内JavaScript。

```json
{
  "schema":"home3d.device-state-description.v1",
  "mode":"simulation",
  "summaryRef":{"capabilityKey":"operationState"},
  "qualityRef":{"capabilityKey":"connectionState"},
  "readableRefs":[
    {"capabilityKey":"power"},
    {"capabilityKey":"operationState"},
    {"capabilityKey":"connectionState"}
  ]
}
```

`summaryRef`必须指向readableRefs内的可读属性；`qualityRef`可省略。带分路的引用完整写`controlObjectId/outputId/capabilityKey`，不按同名属性跨分路回退。省略初值表示SDK未知，不用false/0代替未知。控制目标与当前值分开；例如`targetPosition`可写、`position`只读。

派生规则示例：**仅用于明确授权的本地模拟**，开机后把只读运行状态更新为running。还需为关机、停止和异常定义对应规则，避免残留运行效果。

```json
{
  "schema":"home3d.device-behavior-template.v1",
  "version":1,
  "mode":"simulation",
  "rules":[{
    "id":"power-on",
    "when":{"target":{"capabilityKey":"power"},"value":true},
    "actions":[{"capabilityKey":"operationState","operation":"observe","sample":true,"value":"running"}]
  }]
}
```

规则只能引用当前资产已声明的能力，禁止写入固定deviceId或跨设备引用。动作类型、值域、冲突及标准程序合法性仍由锁定SDK验证。数字过渡使用SDK的`transitionMs`；停止需要取消对应过渡，不能只改文字。合并已有Home3D时，追加实例规则并保留原程序、资源及绑定。

## 状态驱动模型

给实际节点/材质/灯光稳定名称，通过合同effect的slot和bindings.template连接。运行状态控制父节点显隐，模式控制蓝/橙/中性子节点，数值控制位移/缩放/透明度；机器人机身和基座分开。发光材质须有非黑emissive颜色，关闭时实际光强也归零。效果材质每实例独立。

预制气流仍只用现有SDK通道。`effects.json`可声明`groupId=sdk-core-state-effects`、`groupVersion=1`及`channels`，入口再声明`sdk-core-effects`特性。此配置不新增原生气流/颜色/旋转指令，也不代表完整产品高级效果已验收。效果仍须通过SDK校验，并在实际执行器中验证。

## SDK读取与验证

```js
const project = await sdk.readPackage(home3dBytes);
const runtime = sdk.createDemoRuntime(project);
const deviceId = project.devices.instances[0].id;
runtime.dispatch({deviceId, capabilityKey:'power', operation:'write', value:true});
runtime.read({deviceId, capabilityKey:'operationState'});
// {known:true, value:'running'}，结果取决于该合同及已装配规则
runtime.effects(); // 通用查看器需把这些指令应用到真实模型
```

需要统一读取时，可显式导入本技能`scripts/device_state.mjs`的`readDeviceState(runtime, deviceId, contract, description)`，也可把模块作为开发资料复制到交付包。它返回summary、可选quality和保留完整作用域的values数组；状态仍由官方SDK持有。查看器不自动执行上传包中的代码。

新交互包的build job至少放两实例。场景不仅触发按钮，还应断言动作后的当前状态、对应效果和B实例不变，例如：

```json
{
  "name":"运行状态及模型反馈",
  "steps":[
    {"action":{"deviceId":"device-a","capabilityKey":"power","operation":"write","value":true}},
    {"expect":{"ref":{"deviceId":"device-a","capabilityKey":"operationState"},"value":"running"}},
    {"expectEffect":{"instanceId":"a","target":{"kind":"node","name":"RunningIndicator"},"channel":"node.visible","value":true}},
    {"expect":{"ref":{"deviceId":"device-b","capabilityKey":"operationState"},"value":"off"}}
  ]
}
```

节点名和期望值按实际模型改写；存在效果时，build要求效果断言，失败时不发布交付目录。最低覆盖开/关或开始/停止、模式切换、运动中间值、异常及错误分路。无空间效果的信息设备用状态面板说明，不编造动画。SDK协议、状态/效果值、Three.js执行、浏览器画面、保存重开、真实硬件分别记录证据。
