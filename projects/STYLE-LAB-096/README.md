# 四风格家具库验证

从原96㎡设计设定派生的独立验证项目；尺寸、费用为示范设定，不代表实测、客户批准或实际选品。项目模型显式记录家具类型、朝向、材料角色及相机。原DEMO-APT-096保持原样。

[四风格总对比](comparison.html)可切换客厅、餐厅、书房及轴测。日式自然、意式现代和中古复古使用相同机位；白模包含额外客厅样板机位，页面明确标注。各风格输出位于visuals/style-variants/，包含PNG、Blender、GLB与实际渲染记录。

最新极简白模 **white-minimal v4** 加强白灰明暗层次、接触阴影和硬质边缘，统一输出6张2400×1800、128采样图。查看[同机位v3→v4清晰度对照](clarity-refinement.html)；当前模型和渲染记录位于 `visuals/style-variants/white-minimal-crisp-v4/`。

家具款式覆盖沙发、茶几、椅子、柜门与吊灯。白模额外细化床品、可识别设备、客厅软包和阔叶植物；普通桌及未知设备仍有基础造型。程序化纹理以Blender为准，GLB保留基础材质与玻璃透射。展示附加物单独记录，不改主模型户型、家具位置或外包尺寸。

历史结果保留：[白模v2参考对比](white-refinement.html)、[v3客厅样板](living-refinement.html)。v3补图目录内的 `render_remaining_views.py` 使用相对路径读取已记录相机及原生场景；`python render_remaining_views.py --check-only`可无渲染核对来源。其记录分别保存原执行脚本哈希与整理后可移植配方的哈希，既有图像哈希不变。

复现命令与适用范围见[风格与家具库](../../skills/interior-orchestrator/references/style-library.md)。这是设计表现验证，未将基础模型或候选渲染视为加工图、客户审批或已实施工程。
