"""Validated style/asset discovery; standard library only, safe to import without Blender."""
import argparse
import copy
import json
import math
import re
from pathlib import Path
from style_presentation import presentation_settings

REFERENCES = Path(__file__).resolve().parent.parent / 'references'
PRESETS_PATH = REFERENCES / 'style-presets.json'
CATALOG_PATH = REFERENCES / 'furniture-catalog.json'
FAMILIES = ('sofa', 'coffee_table', 'chair', 'cabinet_front', 'pendant')
COLORS = ('wall', 'floor', 'wood', 'upholstery', 'metal', 'accent', 'stone', 'shade')
TEXTURES = ('plain', 'wood', 'fabric', 'leather', 'stone', 'plaster')


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'JSON 字段重复：{key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def token(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]*', value)


def load_catalog(path=None):
    data = read_json(path or CATALOG_PATH)
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('不支持的家具库版本')
    assets, profiles = data.get('assets'), data.get('material_profiles')
    if not isinstance(assets, dict) or not assets or not isinstance(profiles, dict):
        raise ValueError('家具库必须包含 assets 和 material_profiles')
    for asset_id, a in assets.items():
        if not token(asset_id) or not isinstance(a, dict) or a.get('family') not in FAMILIES:
            raise ValueError(f'无效资产：{asset_id}')
        if a.get('builder') != a['family'] or not isinstance(a.get('parameters'), dict):
            raise ValueError(f'未知生成器：{asset_id}')
    for name, p in profiles.items():
        if not isinstance(p, dict) or p.get('texture') not in TEXTURES:
            raise ValueError(f'未知材质纹理：{name}')
        for key in ('roughness', 'metallic', 'bump'):
            v = p.get(key)
            if not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1:
                raise ValueError(f'无效材质参数：{name}.{key}')
        if not isinstance(p.get('scale'), (int, float)) or not 0 < p['scale'] < 10000:
            raise ValueError(f'无效纹理尺度：{name}')
    return data


def validate_style(style, catalog):
    if not isinstance(style, dict) or not token(style.get('id')):
        raise ValueError('风格 id 必须是安全的英文标识')
    if not isinstance(style.get('name'), str) or not style['name'].strip():
        raise ValueError('风格缺少名称')
    if type(style.get('version')) is not int or style['version'] < 1:
        raise ValueError('风格版本必须是正整数')
    for role in COLORS:
        color = style.get('colors', {}).get(role)
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
            raise ValueError(f'{style["id"]} 缺少有效颜色：{role}')
        if style.get('surfaces', {}).get(role) not in catalog['material_profiles']:
            raise ValueError(f'{style["id"]} 未知材质：{role}')
    for role,profile in style.get('surfaces',{}).items():
        color=style.get('colors',{}).get(role)
        if profile not in catalog['material_profiles'] or not isinstance(color,str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}',color):
            raise ValueError('附加材质角色无效：'+role)
    for family in FAMILIES:
        aid = style.get('forms', {}).get(family)
        asset = catalog['assets'].get(aid)
        if asset is None or asset['family'] != family:
            raise ValueError(f'{style["id"]} 未知或类型不符的资产：{family}={aid}')
    lighting = style.get('lighting', {})
    if not isinstance(lighting.get('cct_k'), (int, float)) or not 1800 <= lighting['cct_k'] <= 6500:
        raise ValueError('风格灯光色温必须在1800至6500K之间')
    if not isinstance(lighting.get('ambient_strength'), (int, float)) or not .05 <= lighting['ambient_strength'] <= 2:
        raise ValueError('无效环境光强度')
    presentation_settings(style)
    return style


def load_styles(path=None, catalog=None):
    data = read_json(path or PRESETS_PATH)
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('不支持的风格配置版本')
    items = data.get('styles')
    if not isinstance(items, list) or not items:
        raise ValueError('styles 必须是非空列表')
    catalog = catalog or load_catalog()
    result = {}
    for style in items:
        validate_style(style, catalog)
        if style['id'] in result:
            raise ValueError(f'风格 id 重复：{style["id"]}')
        result[style['id']] = style
    return result


def get_style(style_id):
    styles = load_styles()
    if style_id not in styles:
        raise ValueError(f'未知风格：{style_id}；可选：{", ".join(styles)}')
    return copy.deepcopy(styles[style_id])


def main():
    p = argparse.ArgumentParser(description='查看并校验室内风格预设')
    p.add_argument('--style')
    a = p.parse_args()
    try:
        if a.style:
            print(json.dumps(get_style(a.style), ensure_ascii=False, indent=2))
        else:
            for style in load_styles().values():
                print(f'{style["id"]}  {style["name"]}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(1, f'风格读取失败：{exc}\n')


if __name__ == '__main__':
    main()
