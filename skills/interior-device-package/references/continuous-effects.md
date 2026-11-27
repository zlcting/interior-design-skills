# 持续效果与状态交接

出风、喷雾和运行脉动可以持续播放；窗帘开合、机器人回座是需要等到目标的有限动作。两者由SDK统一执行，使用不同的完成条件。不要用无限experience规则让持续效果一直占用有限过渡，也不要靠设备类型、`fxPhase`名称或超时猜测分类。

## 设备声明

目标SDK至少0.3.4，`target.requiredCapabilities`包含`device.visual-cycles.v1`，并按交互设备交付状态说明。只读相位连接实际模型的变化linear效果：

```json
{
  "id": "running-flow",
  "target": {"capabilityKey": "flowPhase"},
  "when": {"target": {"capabilityKey": "operationState"}, "value": "running"},
  "from": 0,
  "to": 1,
  "durationMs": 1800
}
```

将此项放在`device-contract.json`的`simulation.visualCycles`数组。`flowPhase`是number、access=read、initialValue=0，范围覆盖两个不同端点；周期1—60000ms。when指向同一设备的独立可读属性，完整保留controlObjectId/outputId；不包含deviceId。名称和1800ms只是样例，按实际效果声明。

presentation.effects使用相位作为source，以变化linear映射驱动已有位移、缩放、透明度或光强通道，并通过slot连接模型目标。纯信息设备无需虚构持续动画。

开关到operationState等模拟派生规则保留在behavior模板。停止、离线、异常时让gate变为非运行或未知；SDK停止并复位视觉相位。不要用命令、动作或initialState写相位，不以相位触发业务规则或另一循环。非法合同仍由SDK拒绝。

## 装配与客户端

- 装配时原样保留合同声明；资产与Home3D清单都必须带所需能力。旧SDK应明确拒绝，不通过删能力、关动效或改成静态包绕过。
- `hasPendingTransitions()`包含持续视觉效果，用于设备帧调度。`hasBlockingTransitions()`只查询有限运动；讲解状态及最终帧回执还需独立检查。不要用pending作为禁止讲解或状态交接的条件。
- 讲解通过startGuidedScene与最终帧确认；稳定交接调用exportStableState/importStableState。SDK重建视觉周期，不重放命令或业务规则。不要在宿主复制设备状态机。
- 暂停讲解或后台冻结活动时间；取消/替换讲解保留仍满足gate的持续效果。稳定状态交接不等于在途窗帘/讲解队列的检查点恢复。

## 验证

build对包中每个已声明周期使用独立gate样本，通过SDK检查相位推进、持续帧需求、不阻塞讲解末态、稳定交接及未知gate停止，结果写入acceptance.continuousEffects。样本通过不代表开关规则正确，也不代表画面可见或材质隔离已审。

job中仍需验证真实声明的控制路径：开启设备→当前运行状态与模型反馈、持续效果中执行有限动作、确认末态、交接后继续、关闭/异常，以及第二实例不被操作串改。steps在原有action/advanceMs/expect/expectEffect之外支持：

| 步骤 | 用途 |
|---|---|
| `runtime: "resume"`等 | resume/pause/background/foreground/restart/cancelGuidedScene |
| `guidedScene: {id, actions}` | 沿用SDK讲解合同；actions是映射到实例的标准动作 |
| `expectGuidedStatus` | 断言running/awaiting-presentation/completed等状态 |
| `acknowledgeGuidedFrame: true` | 当前最终帧必须存在，再确认 |
| `expectPendingTransitions` | 断言是否仍需设备帧 |
| `expectBlockingTransitions` | 断言是否还有有限运动 |
| `handoff: true` | 导出稳定状态至新SDK会话，断言属性和投影效果一致 |

handoff后新会话按SDK默认paused状态创建；下一次讲解先resume。声明时长、规则引发的有限运动和最终帧尚未确认时，交接仍应失败；工具不会为了验收通过自动取消它们。浏览器、真实编辑保存和手机端验证另行记录。

## 迁移已有包

先核对实际冻结合同与规则，不按设备显示名称批量替换。保留模型、能力作用域、deviceId/instanceId、安装位置、业务模板引用和光影；只更新明确确认的持续效果合同及相关规则。

将相位改为只读并声明visualCycles，删除相位重复规则及旧相位写入/停止，保留控制到运行状态的派生。收窄已有写权限须升级资产/合同主版本；同步实际源ZIP摘要、合同内容地址和文件清单，经SDK writer生成新包，保留原包。工程变化后重绑定experience/rendering的projectDigest，业务发布引用同一新摘要；不能覆盖旧哈希路径下的文件。技能更新不自动上传DEV或升级小程序。
