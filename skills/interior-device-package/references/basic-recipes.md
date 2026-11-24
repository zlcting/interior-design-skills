# 灯与窗帘的基础配方

下面的字段已按SDK0.3.0组织。它们说明基本做法，不代表真实产品参数或高级效果已经实现。包外的制作源文件保留，实际尺寸和能力来自任务。建模可用项目已有工具（如Blender），导出自包含GLB后读取实际边界，不能以截图代替模型。

## 模型定义与坐标

通过锁定SDK的`inspectModel(glbBytes, file)`取得bounds。以实际min/max计算defaultSize；单位比例已是米且未旋转时，normalization为`{translation:[-(minX+maxX)/2,-minY,-(minZ+maxZ)/2],scale:[1,1,1]}`。若需要旋转或其他单位，先在制作工具烘焙后重查几何。

model.json字段为schema=`home3d.model-definition.v1`、kind=`model`、file、defaultSize、pivot=`bottom-center`、normalization、targets；实际照明另加lightingPath。不要把世界坐标混进局部锚点。灯光sidecar按模型作者空间记录，安装点按归一化局部空间记录。

## 灯：开关和亮度

制作独立发光材质`LampEmitter`，不要让整盏灯一起发光。需要照亮房间时另交`home3d.model-lighting.v1`，包含modelDigest、right-handed-y-up和fixtures；fixture的id例如`MainPoint`。color、maxIntensity、initialBrightness、initialCctK、rangeM和emitterOffsetM按任务确认，首版基础点光使用固定颜色。

合同骨架如下；省略的模拟数组保持空，不表示有硬件控制：

```json
{
  "schema":"home3d.device-contract.v1","id":"asset.lamp","version":"1.0.0","name":"灯模拟",
  "scopes":[{"capabilities":[
    {"key":"power","behavior":"property","access":"read-write","value":{"type":"boolean"},"initialValue":false},
    {"key":"brightness","behavior":"property","access":"read-write","value":{"type":"number","minimum":0,"maximum":100,"unit":"%"},"initialValue":50}
  ]}],
  "presentation":{"controls":[
    {"id":"power","label":"开关","widget":"toggle","source":{"capabilityKey":"power"}},
    {"id":"brightness","label":"亮度","widget":"slider","source":{"capabilityKey":"brightness"}}
  ],"effects":[
    {"id":"emission","source":{"capabilityKey":"brightness"},"enabledBy":{"capabilityKey":"power"},"slot":"emitter","channel":"material.emissiveIntensity","mapping":{"kind":"linear","input":[0,100],"output":[0,2]}},
    {"id":"illumination","source":{"capabilityKey":"brightness"},"enabledBy":{"capabilityKey":"power"},"slot":"point","channel":"light.intensity","mapping":{"kind":"linear","input":[0,100],"output":[0,55]}}
  ]},
  "simulation":{"behavior":"state-transition.v1","transitions":[],"commands":[]}
}
```

示例强度2/55是模拟配方值，须按实际照明调整和视觉验收。模板slot=emitter指向`{kind:"material",name:"LampEmitter"}`，slot=point指向`{kind:"light",name:"MainPoint"}`；model.targets声明该材质，light目标由sidecar提供。测试关闭无残光、0/50/100亮度、两台灯互不影响。

## 帘：开度和停止

左右帘片独立节点，原点放在各自外侧轨道固定端；沿局部X缩放时收拢不漂移。布帘与纱帘使用不同材质，双轨作为两台可独立控制设备。固定样例不能冒充任意窗洞程序化资产。

合同包含position：number、read-write、范围0—100、unit=%、模拟初值0；stop：command、write、value.type=null，无initialValue。controls分别使用slider和button。约定0全关、100全开，必须与产品开度方向核实。

两个effects分别绑定left/right，channel=node.scale.x；mapping为linear，input=[0,100]，output=[1,0.14]。0.14为样例收拢比例，不代表所有帘布。模板分别指向真实LeftPanel/RightPanel节点，model.targets也声明这些节点。

```json
{
  "behavior":"state-transition.v1",
  "transitions":[{"target":{"capabilityKey":"position"},"durationMs":2400}],
  "commands":[{"source":{"capabilityKey":"stop"},"effects":[{"operation":"stop","target":{"capabilityKey":"position"}}]}]
}
```

2400ms是显式演示时长，不能替代真实反馈。测试write position=100，advance 1200后应为50，execute stop value=null，再advance 5000仍为50；另一台帘保持初值。真实模式使用当前开度反馈、约300ms显示插值，需另实现反馈适配，不能直接沿用模拟器。
