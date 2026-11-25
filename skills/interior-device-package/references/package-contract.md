# 设备包约定

## 入口与文件

源格式`home3d.device-asset.v1`、specVersion=`1.0.0-draft`是项目评审约定，与标准home3d.package.v4分开。工具实现下面的基础配置及可选标准experience状态规则，不代表所有效果和真实状态政策已经执行。

```text
device-source/
  device-asset.json
  model.json
  device-contract.json
  bindings.template.json
  device-state.json          新交互包必需：可读状态及摘要引用
  behavior.template.json     需要派生状态/时序时
  rig.json
  state-policy.json
  effects.json
  sources.json
  assets/model-lod1.glb
  assets/lighting.json       有实际照明时
  preview.png
  README.md
  parameters.json            程序化/路径时
  source/                    可另交并说明位置
```

| 入口字段 | 要求 |
|---|---|
| id/version/name | id以字母开始、最多128位，由字母数字及`_.:-`组成；版本x.y.z，不覆盖发布版本 |
| deviceType/geometryKind | 设备类型；fixed/procedural/path |
| requirementRef | modelTypeId和templateKey对应scope.json；超出首批时scopeStatus=experimental并写reason |
| entries | model/contract/bindings/rig/statePolicy/effects/sources/preview指向对应文件；新交互包加stateDescription，规则加behavior |
| target | packageVersion=4、sdkVersion=0.3.0或0.3.1、profile=core-v4、requiredCapabilities数组；客户端验收另锁定版本 |
| requiredFeatures | `{id,version}`数组；version=1的device.static、light.power、light.brightness、curtain.position、curtain.stop，以及新交互包的device.state-simulation、通用效果的sdk-core-effects |
| files | 完整登记path/byteSize/digest，入口自身除外；sha256:加64位小写十六进制 |

seal只刷新清单，不证明功能正确。禁止绝对/越界路径、反斜线、重复路径、符号链接和外部纹理；包内代码不作为运行入口。ZIP根目录直接含入口，验收结果放ZIP外避免摘要循环。破坏坐标/单位/能力/slot或收窄参数范围升级主版本，兼容增项升级次版本，兼容修复升级修订版本。

## 配置语义

model.json和device-contract.json遵循锁定SDK严格Schema。defaultSize与normalization对应实际GLB，targets指向真实目标；lightingPath的sidecar摘要绑定该GLB。不要向SDK定义加质量或高级时序字段。

bindings.template.json：home3d.presentation-template.v1，bindings每项只有slot/target，装配时补deviceId。状态描述和相对规则格式见[能力、状态与SDK配方](capabilities-and-state.md)；装配规则自动声明experience.references.v1，并保留原工程规则。

rig.json：home3d.device-rig.v1，coordinateSpace=normalized-model，front=[0,0,-1]；mounting包含allowedSurfaces和attachmentPoint。anchors记录功能位置/方向/范围，parts连接真实节点/材质。job.position是最终实例原点，安装点应先经实例缩放与旋转，再从目标安装位置扣除。

state-policy.json：home3d.device-state-policy.v1，记录mode、来源、当前/目标角色、质量与异常策略。首版只接受simulation；其他策略保留为制作资料，不冒充已执行的真实反馈适配。

effects.json：home3d.device-effects.v1，effects数组记录groupId/groupVersion、inputs、rig引用与所需功能。支持point/curtain及sdk-core-state-effects组、基础visible、position/scale各轴、opacity、emissiveIntensity、light.intensity通道；静态设备可空数组。sdk-core-state-effects需列出实际channels并声明sdk-core-effects特性；气流可使用预制网格和已有通道组合。未增加私有颜色/色温、面光、旋转指令；原生高级效果仍需消费者支持。

sources.json：home3d.device-sources.v1，包含requirements、product、capabilityMappings、tools，记录产品尺寸/许可依据、来源摘要、源template/relation到完整能力作用域的转换和确认状态。不明映射写needs-mapping，不分发凭据或整张无关业务表。

程序化/路径资产另交home3d.device-parameters.v1，含generatorId/version、参数/单位/范围、实例输入和输出语义，同输入输出确定。首版会阻止这些源包进入固定模型装配路径，不静默丢弃生成语义。

## build job

job是本地制作输入，路径相对job目录，outputDir必须不存在且不在源目录内。

```json
{
  "assetDir": "./lamp-source",
  "outputDir": "./lamp-delivery",
  "name": "落地灯测试",
  "placements": [
    {"instanceId":"lamp-a","floorId":"floor-test","roomId":"room-test","placement":"floor","position":[-1,0,0]},
    {"instanceId":"lamp-b","floorId":"floor-test","roomId":"room-test","placement":"floor","position":[1,0,0]}
  ]
}
```

不指定basePackage时创建测试房间。指定basePackage时用原工程的真实楼层/房间ID。rotation默认单位四元数，size默认模型尺寸。首版只支持floor/wall/ceiling自由放置；宿主/开口安装需另实现，不能以null冒充。consumerCapabilities可给目标消费者实际能力数组；未给时只证明SDK协议，不宣称客户端支持。

scenarios含name和steps；每步可提供action（deviceId及完整scope/capabilityKey/operation/value）、advanceMs、expect（ref/value），或expectEffect（instanceId/target/channel/value），通过SDK模拟器断言。效果选择器须唯一匹配。execute无参数仍传value:null。新device.state-simulation包的build要求至少两实例和状态断言；合同含效果时还要求效果断言。旧源包继续可检查，不能以旧包验证结果替代新要求。

输出`<id>-<version>.device.zip`、validation.home3d、acceptance.json。合并既有工程时保留原必需能力、资源、合同、experience和rendering，重绑定projectDigest，并给新模型灯声明阴影策略。

依赖同组interior-home3d的锁定SDK制品；独立部署可运行：

```sh
node scripts/device_package.mjs build /path/to/job.json --sdk-dir /path/to/interior-home3d/scripts/vendor
```

源包检查只处理新增入口和制作边界；Home3D/GLB/合同/绑定验证都交由SDK。
