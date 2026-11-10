# 多风格三维与家具库

## 范围与入口

四套预设：日式自然 japanese-natural、意式现代 italian-modern、中古复古 mid-century、极简白模 white-minimal。
`style-presets.json` 负责搭配；`furniture-catalog.json` 持有16款参数化资产和材质配置；`scripts/furniture_library.py` 将资产生成局部毫米构件；`style_renderer.py` 负责Blender场景及导出。`style_plan.py` 可在普通Python中完成输入、引用和构件外包尺寸检查。

第一版差异覆盖沙发、茶几、椅子、柜门与吊灯。基础模式中的床、普通桌、书桌、地毯及设备使用基础造型，清单的 basic_objects 明确列出；白模illustrated模式会额外细化床及可识别设备，仍未识别的设备保留外包体积。不能据此声称所有家具均已精细建模，也不代表实际品牌选品或加工图。

## 项目模型

模型仍以 `model/project.json` 为主件。家具保留id、rect、height_mm、material，新增：

- `furniture_type`：sofa / coffee_table / chair / cabinet_front；基础类型 bed / table / desk / rug / equipment。
- `facing`：south / north / west / east，表示使用者面对家具的正面方向。局部X为正面宽度、局部Y从正面向背面，朝向改变只旋转局部构件，不改变项目外包rect。
- `asset_id` 可选，显式覆盖风格选款，必须与家具类型一致。
- 柜体 `countertop:true` 可生成石质台面，尺寸仍包含于原外包高度。
- 材料 `style_role` 将对应材料关联到 wall / floor / wood / upholstery / metal / accent / stone / shade。不设置的材料保留项目原色。
- 吊灯显式设置 `fixture_type:"pendant"`；可以设置asset_id。当前吊灯资产的安装外包为1100×400×950mm，`z_mm` 为灯体最低点；放不下层高会拒绝生成。
- `visualization.style_id` 为项目默认风格；命令行 --style 用于候选比较，不自动改写项目选择。
- `visualization.cameras` 为相机列表，含name、location、target，坐标米；可选lens、type=ORTHO、ortho_scale。新户型必须准备自己的相机。

显式字段示例：`{"id":"LOUNGE-A","furniture_type":"sofa","facing":"west","rect":[2600,650,900,2600],"height_mm":800,"material":"FABRIC","kind":"furniture"}`。

仅原DEMO-APT-096由命名的兼容适配器补足类型、材料角色和相机；新项目不能照搬它的编号。STYLE-LAB-096是单独的设计设定验证项目，已经显式填写所有字段。原96㎡交付文件及用户此前的配色预览保留。

## 选择与生成

在工程根运行（安装后也可使用对应scripts绝对路径）：

```bash
python3 skills/interior-orchestrator/scripts/style_library.py
python3 skills/interior-orchestrator/scripts/render_project.py projects/STYLE-LAB-096 --style mid-century --check-only
blender -b -t 4 --python-exit-code 1 --python skills/interior-orchestrator/scripts/render_project.py -- projects/STYLE-LAB-096 --style mid-century
```

可用 --view living/dining/study/axon 或all；名称取自项目相机，多个视图用逗号分隔。白模v3另提供按客厅家具推导的living-detail与living-close。其他三种风格默认32采样、1200像素宽；白模v4默认128采样、2400像素宽，命令行参数可覆盖；--out可指定独立输出。只检查模式不导入Blender、不创建输出目录。未选择风格且模型没有默认风格时，仍走原案例流程；该旧流程只适用于原示范。

完整风格输出为 `visuals/style-variants/<风格id>/`，与此前 `style-previews/` 的配色试验分开。每个目录含实际视图PNG、interior.blend、interior.glb、输入原文、补足语义后的resolved-input.json及render-manifest.json。重新生成同一风格将更新该目录；需保留历史时用--out指定新目录。

记录包含输入哈希、风格快照、家具库哈希、生成器哈希、实际选用资产、基础对象、材质参数、相机与输出哈希。GLB保留几何及基础颜色/粗糙度/金属度；程序化纹理以.blend与PNG为准，当前不提供纹理烘焙。风格候选不自动改写正式材料表、报价或预算，采纳后需同步相关设计与费用。

## 扩展

添加已有家具类型的新款式：在catalog.assets里复制同类型资产、改变parameters，再从风格forms或家具asset_id引用。现有生成器支持的参数变化不需要改渲染脚本。新增几何算法或全新家具类型则需要扩充生成器及行为测试；不能用一个未实现的名称冒充支持。

添加风格：在预设中定义唯一id、版本、colors、surfaces、forms和lighting。surfaces引用材质库，forms引用相应类型的资产。未知款式、类型不符、缺语义、构件越界和非法颜色均应在渲染前报错，不悄悄回退为原木风。

## 验证

`python3 -m unittest discover -s tests -v` 覆盖选择、编号更换、四种朝向、外包尺寸、错误拒绝、扩展款式与原流程回归。运行Blender实际生成并检查代表视图；单元测试通过不等于视觉通过。材质风格应采用相同相机、尺寸和采样设置；白模可以通过显式presentation配置调整轴测留白与墙体显示，分别检查轮廓、材质及灯具。


## 极简白模 white-minimal

适合参考图中白色建筑模型、简洁家具、蓝色背景的空间汇报。命令选择 `--style white-minimal`，推荐先用 `--view axon`。白模复用已有简洁家具资产，同时启用统一哑光浅色、连续地面、蓝灰玻璃、蓝色衬底和柔和阴影；不改户型、门窗、家具位置或权威材料数据。前三种风格的参数保持原样。

`presentation` 为可选显示配置：

- `material_mode:clay`：覆盖包括未绑定style_role的材料及设备，避免原有木纹、深色金属或设备颜色漏入白模。它是表现方式，不是现实白色装修材料选品。
- `background_color`、`ground_plane`、`foundation`：控制蓝色衬底、承接阴影的环境平面和白色模型底座。环境平面只留在Blender/PNG中，GLB不导出大面积背景。
- `floor_joints:false`：关闭木地板和瓷砖拼缝。
- `glazing_color`、`glazing_roughness`、`glazing_transmission`：蓝灰玻璃外观。
- `cutaway_mode:camera`：轴测视图根据相机方向保留远端外墙完整高度，近端和内墙降到cutaway_height_mm。低墙上的玻璃同步截断，不悬浮。透视仍使用完整墙体。
- `exposure`、`contrast`：白模亮度与明暗层次。
- `orthographic_margin`、`orthographic_target_lift_mm`：轴测构图留白与目标高度，只影响渲染时相机；不改项目相机原值。

白模的.blend默认打开轴测剖切场景，GLB导出相应剖切墙体、家具和底座。前低后高是表现剖切，不是墙体实际高度变更。示范户型仍是96㎡案例，不复制参考图的房间布局或未提供尺寸。

校验新白模：`python3 tools/verify_style_outputs.py projects/STYLE-LAB-096 --style white-minimal --require-current`。不加--style会核对全部风格的输入、相机、资产、文件哈希和GLB，并明确标记旧生成器产生的历史预览；历史记录不会被新代码静默改写。


### 白模v2：建筑模型插画表现

`white-minimal`预设升级到version 2。采用 `lighting_rig:studio` 的平行主光与大面积补光，避免蓝色衬底因距离衰减而一侧过暗；`contact_shadow_strength`与`contact_shadow_distance_mm`控制接触处层次，`aspect_ratio`控制输出比例（白模4:3）。原三种材质风格保留daylight默认配置。

`detail_level:illustrated` 启用可选白模细节模块 `white_details.py`：床品分层与软枕、圆润软包、冰箱分门、洗烘机圆窗、坐便器及明确记录的展示附加物。设备优先读取家具equipment_type（refrigerator/washer_stack/toilet）；旧示范通过已有的设备名称/对象关联兼容，未知设备保持基础体块。厨卫点位及淋浴使用现有equipment.xy、countertop与model.shower，不另建一套工程位置。

新增 cone-shade 锥形吊灯资产及暖色灯泡。少量电视、盆栽、台面细节属于 `accessories:true` 的表现附加物，按已存在的台面/设备位置放置，逐项记录source_object/source_equipment；它们不自动成为已批准的采购或施工对象。关闭accessories可以移除附加物；关闭illustrated可恢复基础造型。

原始户型、家具外包rect和主模型尺寸不变。此前笼统归为基础造型的床和已识别设备在本模式下标记refined-basic；清单分别记录refined_objects、accessories及剩余basic_objects。`white-minimal-v1/`保留上一版结果；工程中的 `projects/STYLE-LAB-096/white-refinement.html`用于人工视觉复核。

### 白模v3：客厅局部样板

`presentation.living_refinement:true`需要illustrated模式。`living_details.py`按同房间中茶几与最近沙发配对，仅细化该组合，保留其他房间家具和全部主模型外包。沙发采用三维矩形软包、独立坐垫、方形抱枕及细滚边；茶几采用薄台面、细腿和内收支撑。`illustration_meshes.py`生成可在普通Python中校验边界的曲面网格，不使用圆片代替抱枕。茶几上的盆栽替换为有弧度的阔叶和茎。

可选落地灯在沙发端部寻找房间内部、与现有家具不相交的位置，找不到时跳过。落地灯和植物均记录source_object、presentation_only；不新增工程灯位或采购项目。灯罩为开口薄壳，暖色发光面与实际区域光源同时构成局部暖光。玻璃使用高透射、低粗糙度与阴影透光，窗框补齐横向细框；摄影棚主光、补光及接触阴影一并调整。前三种风格的显示默认值保持原状。

两个推导视图只存在于表现层：`living-detail`为客厅轴测，其近端展示墙降至300mm以看清家具；`living-close`为客厅透视。主模型相机、墙体和门窗尺寸均不改写。它们与主模型相机同名时尊重主模型已有视图。

本轮候选输出独立保存，不覆盖v2：

```bash
blender -b -t 6 --python-exit-code 1 --python skills/interior-orchestrator/scripts/render_project.py -- projects/STYLE-LAB-096 --style white-minimal --view axon,living-detail,living-close --width 1600 --samples 96 --out projects/STYLE-LAB-096/visuals/style-variants/white-minimal-living-v3
python3 tools/verify_style_outputs.py projects/STYLE-LAB-096 --style white-minimal --out projects/STYLE-LAB-096/visuals/style-variants/white-minimal-living-v3 --require-current
```

输出核验支持选择视图，不要求每次渲染所有相机。历史预览按其已记录的风格快照核对并明确标记historical；`--require-current`要求当前风格、生成器、计划与输出哈希全部一致。客厅样板的前后对照见 `projects/STYLE-LAB-096/living-refinement.html`。

### 白模v4：清晰度与硬质边缘

`white-minimal` version 4收紧硬质表面并提高白灰层次。`presentation.hard_edge_bevel_mm`限制box形墙面、柜门、桌板、金属构件及玻璃细框的倒角，平面转角半径不超过该值的4倍；沙发软包、枕头、床品与植物曲面保持原造型。转换发生于表现层，不修改家具rect、主模型或前三种风格。生成的Blender对象记录hard_edge_bevel_mm，校验器检查实际Bevel宽度。

`studio_key_strength`、`studio_key_angle`与`studio_fill_scale`控制主光和补光比例；短距离接触阴影增强缝隙、支脚和转角层次。白模地面统一使用floor角色；墙、地面、硬质家具与软包采用不同浅灰明度。`pixel_filter_width:1.0`减少细线的滤波软化，仍保留抗锯齿。正式图不加后期锐化。

`default_render_width:2400`与`default_render_samples:128`成为白模的默认质量（4:3，2400×1800）。命令行`--width`、`--samples`始终优先；其他三种风格仍默认1200宽、32采样。`--check-only`会打印实际质量，不导入Blender。

`--device auto`在当前Blender进程中优先启用可用GPU（Metal/CUDA/OptiX等），无可用设备时使用CPU；不保存全局偏好。省略该参数仍使用CPU。`--no-denoise`供同机位小样对照，正式输出保留降噪并记录实际设备、滤波宽度及质量。Blender文件使用相对渲染保存路径，移动成果目录后可继续打开渲染。

```bash
blender -b -t 6 --python-exit-code 1 --python skills/interior-orchestrator/scripts/render_project.py -- projects/STYLE-LAB-096 --style white-minimal --device auto --out projects/STYLE-LAB-096/visuals/style-variants/white-minimal-crisp-v4
python3 tools/verify_style_outputs.py projects/STYLE-LAB-096 --style white-minimal --out projects/STYLE-LAB-096/visuals/style-variants/white-minimal-crisp-v4 --require-current
```

本轮6张视图统一高分辨率生成。`comparison.html`白模图片与模型均指向v4；`clarity-refinement.html`对照v3/v4同机位轴测与客厅。v1、v2、v3及v3补充图保留。

## 交换几何验收

新版生成器通过 `exchange_validation.py` 显式应用修改器并重新导入GLB，输出 `exchange-validation.json`。当前版本核验要求报告与最终GLB哈希一致，逐对象求值几何在声明容差内匹配。缺少此报告的历史输出标记为交换几何未验，不补造历史通过。渲染/网页对照与独立HTML要求见[三维交换与网页验收](../../interior-visualization/references/exchange-acceptance.md)。

## 生成前的选择提示

使用本流程前执行[家具精细度与风格选择](3d-selection.md)。精细任务需实际经过 `resolve_plan` 的 `refine_furniture`、`refine_living` 与 `detailed_mesh` 等适用模块，并记录解析结果；仅标注white-minimal或修复导出倒角不能替代精细模型。既有明确选择说明沿用，不重复询问。
