# 状态与验收

## 状态来源

- property注明类型/范围/单位/枚举/权限；command只写、event只读。初值只用于属性，模拟初值不作为硬件事实。
- 当前开度/高度/运行状态与目标值、write/execute指令分开。发送成功不表示已到位，无参数execute仍传value:null。
- 绑定包含deviceId及适用的controlObjectId/outputId/capabilityKey，不按同名跨分路回退；源template/relation/转换/版本写入sources。
- valid/unknown/offline/stale是质量，fault/alarm另设状态。采样有来源、时间和产品确认的过期阈值。未知不填0/false，历史报警事件不锁存为当前报警。
- 首次载入显示当前状态，不补播历史/重复事件。真实反馈只显示插值，无更新不继续朝目标移动。后台冻结模拟，恢复先刷新真实状态；减少动态时用静态结果和文本。

锁定SDK提供known/value、模拟和标准experience规则，完整质量生命周期及硬件反馈适配仍需另实现。工具拒绝real模式；模拟中派生的running、在座和充电不是硬件遥测。

## 分层验收

| 层级 | 最低证据 |
|---|---|
| 来源 | 形态ID、产品尺寸/许可、能力依据；不把待确认项说成实测或已适配 |
| 几何 | 单位/原点/正面、唯一目标、锚点/LOD/预算；变换后标定正确 |
| 源包与v4 | 文件/摘要/引用、坏输入拒绝、SDK真实校验、重复构建一致 |
| 状态 | 操作后用SDK读取当前值，正常/边界/错误分路/停止/无反馈/异常，两实例独立 |
| 渲染 | 材质隔离、关灯无残光、效果随变换、布纱独立、百叶两轴独立 |
| 编辑往返 | 保存/重开/导出重导入，原对象、资源、绑定、光影保留 |
| 服务与硬件 | 指定客户端/URL/包摘要的在线保存与真实反馈联调，分别报告 |

负例包括缺文件、错摘要、越界路径、重名/断裂目标、类型/范围错误、通道冲突、缺必需能力、未知变0、命令被当反馈、共享材质串状态。机器人加测异常取消与回充不归座；事件不作为持续报警。

结果使用passed/failed/blocked/not-reviewed并附证据。build报告sdkStateRead初始读取结果及声明场景的状态/效果断言；SDK.effects()值检查不等于真实画面；stateIsolation仅SDK状态，materialIsolation/editorReview/onlineSave/realHardware默认not-reviewed，不手工盖章。

预览另测首帧、设备切换和后台恢复。帧循环只使用RAF时间戳，首帧推进0，间隔有限且非负，长暂停后重新计时；SDK每次advance仅接受0—60000ms。不得把离线图、Node对象检查或脚本语法通过写成真实浏览器渲染验收。

有持续效果时按[持续效果与交接](continuous-effects.md)声明并验收：持续帧可保持pending，不能阻塞另一个有限动作或稳定状态交接；运动与最终帧未完成时仍需等待。build自动gate样本只证明SDK生命周期，实际开关/异常、效果可见性及客户端交接由各层另验。

## 规范来源

阅读说明：https://ywjb3x2kfn.feishu.cn/wiki/Q6Osw0qA2ieNfAk1im5c4K8Bnhe

开发附录：https://ywjb3x2kfn.feishu.cn/docx/S5nud3W1yokgc2xEEuKchJ9qnif

技能自带范围和方法快照，生成不要求飞书登录。源《设备模型与渲染效果需求评审包-20261123》基线599b6cdf4e4131afaee302e9f257c1da64993b71，摘要见scope.json。原始2576条能力关系只用于追溯，不是可运行合同，也不随技能分发。
