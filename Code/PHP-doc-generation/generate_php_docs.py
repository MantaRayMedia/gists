import os
import re
import yaml
import argparse


def extract_info_yml(path):
    with open(path, 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)
        return {
            'name': info.get('name', os.path.basename(path)),
            'description': info.get('description', 'No description provided.')
        }


def clean_docblock(docblock: str):
    """Parse a PHPDoc block and extract description, parameters, returns, and properties."""
    if not docblock:
        return {
            'description': '',
            'params': [],
            'returns': None,
            'properties': []
        }

    # First extract properties from the "Properties:" section
    properties = []
    property_section = re.search(
        r'Properties:\s*\n(?: \* (.*)\n)*',
        docblock
    )
    if property_section:
        # Remove the properties section from the main docblock
        docblock = docblock[:property_section.start()] + docblock[property_section.end():]
        # Parse each property line
        property_lines = re.findall(
            r' \* \$(\w+)\s*\(type\s+([^)]+)\):\s*(.*)',
            property_section.group(0)
        )
        for name, type_, desc in property_lines:
            properties.append({
                'name': name,
                'type': type_,
                'description': desc.strip()
            })

    # Now process the rest of the docblock normally
    lines = [line.rstrip() for line in docblock.strip().splitlines()]
    description_lines = []
    params = []
    returns = None

    current_tag = None
    current_tag_content = []

    def flush_current_tag():
        nonlocal current_tag, current_tag_content, params, returns
        if current_tag == '@param':
            full_text = " ".join(current_tag_content).strip()
            match = re.match(r'@param\s+(\S+)\s+(\$\S+)\s*(.*)', full_text)
            if match:
                param_type, param_name, param_desc = match.groups()
                params.append({
                    'name': param_name,
                    'type': param_type,
                    'description': param_desc
                })
        elif current_tag == '@return':
            full_text = " ".join(current_tag_content).strip()
            match = re.match(r'@return\s+(\S+)\s*(.*)', full_text)
            if match:
                return_type, return_desc = match.groups()
                returns = {
                    'type': return_type,
                    'description': return_desc
                }

        current_tag = None
        current_tag_content = []

    for line in lines:
        stripped = line.lstrip(" *")

        if stripped.startswith('@param'):
            if current_tag:
                flush_current_tag()
            current_tag = '@param'
            current_tag_content = [stripped]
        elif stripped.startswith('@return'):
            if current_tag:
                flush_current_tag()
            current_tag = '@return'
            current_tag_content = [stripped]
        elif stripped.startswith('@'):
            if current_tag:
                flush_current_tag()
            current_tag = None
            current_tag_content = []
        else:
            if current_tag and stripped != '':
                current_tag_content.append(stripped)
            elif not current_tag:
                description_lines.append(stripped)

    if current_tag:
        flush_current_tag()

    # Clean up description by removing extra whitespace
    description = " ".join(description_lines).strip()
    description = re.sub(r'\s+', ' ', description)  # Collapse multiple spaces

    return {
        'description': description,
        'params': params,
        'returns': returns,
        'properties': properties
    }


def extract_php_definitions(file_content):
    """
    Extracts classes, interfaces, traits, and enums with docblocks, attributes and properties.
    """
    # Pattern to match PHP 8 attributes
    attribute_pattern = re.compile(
        r'#\[([\w\\]+)(?:\(([^)]*)\))?\]',
        re.DOTALL | re.MULTILINE
    )

    # Pattern to match class/interface/trait/enum definitions
    definition_pattern = re.compile(
        r"(?:/\*\*(.*?)\*/\s*)?"          # Optional docblock
        r"(?:(?:#\[.*?\]\s*)*)"           # Any number of attributes
        r"(?:abstract\s+|final\s+)?"       # Optional modifiers
        r"(class|interface|trait|enum)\s+" # Type
        r"(\w+)\s*"                        # Name
        r"(?::\s*(\w+))?\s*"              # Optional enum type
        r"(?:extends\s+\w+)?"              # Optional extends
        r"(?:\s+implements\s+[\w\\, ]+)?" # Optional implements
        r"\s*\{",                          # Opening brace
        re.DOTALL | re.MULTILINE
    )

    # Pattern to match methods
    method_pattern = re.compile(
        r"(?:/\*\*(.*?)\*/\s*)?"      # Optional docblock
        r"(?:(?:#\[.*?\]\s*)*)"       # Any number of attributes
        r"(public|protected|private)?" # Visibility
        r"\s*(static\s+)?"            # Static
        r"function\s+(\w+)\s*\(([^)]*)\)", # Name and params
        re.DOTALL | re.MULTILINE
    )

    # Pattern to match enum cases
    case_pattern = re.compile(
        r"/\*\*(.*?)\*/\s*"  # Docblock
        r"case\s+(\w+)\s*=\s*([^;]+);", # Case definition
        re.DOTALL | re.MULTILINE
    )

    # Pattern to match documented properties
    property_pattern = re.compile(
        r"/\*\*(.*?)\*/\s*"           # Docblock
        r"(?:public|protected|private)\s+" # Visibility
        r"(?:static\s+)?"             # Static
        r"(\??\w[\w\\]*(?:\|[\w\\]+)*)\s*" # Type
        r"\$(\w+)\s*"                 # Name
        r"(?:=[^;]+)?;",              # Optional default value
        re.DOTALL | re.MULTILINE
    )

    definitions = []

    for match in definition_pattern.finditer(file_content):
        docblock, def_type, name, enum_type = match.groups()
        clean_doc = clean_docblock(docblock) if docblock else {'description': '_No description available._'}

        # Extract attributes before the definition
        def_start = match.start()
        preceding_text = file_content[max(0, def_start-500):def_start]
        attributes = [
            {
                'name': attr_match.group(1).split('\\')[-1],
                'params': attr_match.group(2) or ''
            }
            for attr_match in attribute_pattern.finditer(preceding_text)
        ]

        # Extract class body
        start = match.end()
        brace_count = 1
        index = start
        while brace_count > 0 and index < len(file_content):
            if file_content[index] == '{':
                brace_count += 1
            elif file_content[index] == '}':
                brace_count -= 1
            index += 1
        body = file_content[start:index]

        # Parse methods
        methods = []
        for method_match in method_pattern.finditer(body):
            method_doc, visibility, static_kw, method_name, _ = method_match.groups()
            method_clean = clean_docblock(method_doc) if method_doc else {'description': ''}

            # Get method attributes
            method_start = method_match.start()
            method_preceding = body[max(0, method_start-200):method_start]
            method_attributes = [
                {
                    'name': attr_match.group(1).split('\\')[-1],
                    'params': attr_match.group(2) or ''
                }
                for attr_match in attribute_pattern.finditer(method_preceding)
            ]

            methods.append({
                'name': method_name,
                'visibility': visibility or 'public',
                'description': method_clean.get('description', ''),
                'params': method_clean.get('params', []),
                'returns': method_clean.get('returns'),
                'attributes': method_attributes,
                'static': bool(static_kw)
            })

        # Parse enum cases
        cases = []
        if def_type == 'enum':
            cases = [
                {
                    'name': case_match.group(2),
                    'value': case_match.group(3).strip(),
                    'description': clean_docblock(case_match.group(1))['description'] if case_match.group(1) else ''
                }
                for case_match in case_pattern.finditer(body)
            ]

        # Parse properties
        properties = clean_doc.get('properties', [])

        # Add properties from inline docblocks
        properties.extend(
            {
                'name': prop_match.group(3),
                'type': prop_match.group(2),
                'description': clean_docblock(prop_match.group(1))['description'] if prop_match.group(1) else ''
            }
            for prop_match in property_pattern.finditer(body)
        )

        # Add properties from type hints (without docblocks)
        type_hint_pattern = re.compile(
            r"(?:public|protected|private)\s+"
            r"(?:static\s+)?"
            r"(\??\w[\w\\]*(?:\|[\w\\]+)*)\s*"
            r"\$(\w+)\s*"
            r"(?:=[^;]+)?;",
            re.MULTILINE
        )

        documented_props = {p['name'] for p in properties}
        properties.extend(
            {
                'name': hint_match.group(2),
                'type': hint_match.group(1),
                'description': 'No description available'
            }
            for hint_match in type_hint_pattern.finditer(body)
            if hint_match.group(2) not in documented_props
        )

        # Build definition
        definition = {
            'type': def_type,
            'name': name,
            'description': clean_doc['description'],
            'methods': methods,
            'properties': properties,
            'attributes': attributes
        }

        if def_type == 'enum':
            definition.update({
                'enum_type': enum_type or 'string',
                'cases': cases
            })

        definitions.append(definition)

    return definitions


def scan_module(module_path):
    result = {}
    info_yml = None

    for file in os.listdir(module_path):
        if file.endswith('.info.yml'):
            info_yml = os.path.join(module_path, file)
            break

    if not info_yml:
        return None

    metadata = extract_info_yml(info_yml)
    result['metadata'] = metadata
    result['classes'] = []

    for root, _, files in os.walk(module_path):
        for file in files:
            if file.endswith(('.php', '.module', '.install')):
                with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    classes = extract_php_definitions(content)
                    result['classes'].extend(classes)

    readme = extract_readme(module_path)
    if readme:
        result['readme'] = readme

    return result


def extract_readme(path):
    readme_path = os.path.join(path, 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines and lines[0].startswith('# '):
                lines = lines[1:]
            return ''.join(lines).strip()
    return None


def slugify(text, is_method=False):
    text = text.lower().strip()
    if is_method:
        # Normalize leading double underscore
        if text.startswith("__"):
            text = "_" + text.lstrip("_")
        text = re.sub(r'[^a-z0-9_]', '', text)
    else:
        text = text.replace(' ', '-')
        text = re.sub(r'[^a-z0-9\-]', '', text)
        text = re.sub(r'-+', '-', text)
    return text


def write_markdown(output_dir, module_name, data):
    filename = os.path.join(output_dir, f"{module_name}.md")

    def anchor(text, is_method=False):
        text = text.lower().strip()
        if is_method:
            if text.startswith("__"):
                text = "_" + text.lstrip("_")
            text = re.sub(r'[^a-z0-9_]', '', text)
        else:
            text = text.replace(' ', '-')
            text = re.sub(r'[^a-z0-9\-]', '', text)
            text = re.sub(r'-+', '-', text)
        return text

    with open(filename, 'w', encoding='utf-8') as f:
        # Module Title
        f.write(f"# {data['metadata']['name']}\n\n")

        # Overview or Description
        if data.get('readme'):
            f.write("## Overview\n\n")
            f.write(data['readme'] + "\n\n")
        else:
            f.write(f"**Description:**\n{data['metadata']['description']}\n\n")

        # Table of Contents
        if data['classes']:
            f.write("## Table of Contents\n\n")
            for cls in data['classes']:
                cls_anchor = anchor(cls['name'])
                type_name = cls['type'].capitalize()
                if cls['type'] == 'enum':
                    type_name = f"Enum ({cls.get('enum_type', 'string')})"
                f.write(f"- [{type_name} `{cls['name']}`](#{cls_anchor})\n")

                if cls.get('cases'):
                    for case in cls['cases']:
                        case_anchor = f"{cls_anchor}__{anchor(case['name'], is_method=True)}"
                        f.write(f"  - [Case {case['name']}](#{case_anchor})\n")

                if cls['methods']:
                    for method in cls['methods']:
                        method_anchor = f"{cls_anchor}__{anchor(method['name'], is_method=True)}"
                        f.write(f"  - [{method['name']}()](#{method_anchor})\n")

                if cls.get('properties'):
                    for prop in cls['properties']:
                        prop_anchor = f"{cls_anchor}__property-{anchor(prop['name'])}"
                        f.write(f"  - [Property ${prop['name']}](#{prop_anchor})\n")

            f.write("\n")

            # Classes & Collapsible Method Sections
            f.write("## Classes\n\n")
            for cls in data['classes']:
                cls_anchor = anchor(cls['name'])
                type_name = cls['type'].capitalize()
                if cls['type'] == 'enum':
                    type_name = f"Enum ({cls.get('enum_type', 'string')})"

                # Add anchor for the class/enum/trait
                f.write(f'<a id="{cls_anchor}"></a>\n')
                f.write(f"### {type_name} `{cls['name']}`\n\n")
                f.write(f"{cls['description']}\n\n")

                # Display properties
                if cls.get('properties'):
                    f.write("#### Properties\n\n")
                    f.write("| Name | Type | Description |\n")
                    f.write("|------|------|-------------|\n")
                    for prop in cls['properties']:
                        prop_anchor = f"{cls_anchor}__property-{anchor(prop['name'])}"
                        name_display = f"${prop['name']}"
                        f.write(f"| <a id='{prop_anchor}'></a>{name_display} | `{prop['type']}` | {prop['description']} |\n")
                    f.write("\n")

                # Display attributes if present
                if cls.get('attributes'):
                    f.write("#### Attributes\n\n")
                    for attr in cls['attributes']:
                        f.write(f"- `#[{attr['name']}]`")
                        if attr['params']:
                            f.write(f"({attr['params']})")
                        f.write("\n")
                    f.write("\n")

                # Display cases for enums
                if cls.get('cases'):
                    f.write("#### Cases\n\n")
                    for case in cls['cases']:
                        case_anchor = f"{cls_anchor}__{anchor(case['name'], is_method=True)}"

                        f.write(f'<a id="{case_anchor}"></a>\n')
                        f.write(f"##### {case['name']}\n\n")
                        f.write(f"- **Value:** {case['value']}\n")
                        f.write(f"- **Description:** {case['description'] or '_No description available._'}\n")
                        f.write("\n---\n\n")
                    f.write("\n")

                # Display methods for all types
                if cls['methods']:
                    f.write("<details>\n")
                    f.write("<summary>Show Methods</summary>\n\n")

                    for method in cls['methods']:
                        method_anchor = f"{cls_anchor}__{anchor(method['name'], is_method=True)}"
                        f.write(f'<a id="{method_anchor}"></a>\n')
                        f.write(f"##### {method['name']}()\n\n")

                        if method.get('static', False):
                            f.write("- **Static method**\n")
                        f.write(f"- **Visibility:** `{method['visibility']}`\n")

                        if method['description']:
                            f.write(f"- **Description:** {method['description']}\n")

                        if method['params']:
                            f.write("- **Parameters:**\n")
                            for param in method['params']:
                                f.write(f"  - `{param['name']}` (`{param['type']}`): {param['description']}\n")

                        if method['returns'] and method['returns'].get('description'):
                            f.write(f"- **Returns:** `{method['returns']['type']}`: {method['returns']['description']}\n")

                        f.write("\n---\n\n")

                    f.write("</details>\n\n")
                elif cls['type'] != 'enum':
                    f.write("_No methods documented._\n\n")

        else:
            f.write("_No classes with docblocks found._\n")


def main(base_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for module in os.listdir(base_dir):
        module_path = os.path.join(base_dir, module)
        if not os.path.isdir(module_path):
            continue

        data = scan_module(module_path)
        if not data:
            continue

        module_machine_name = os.path.basename(module_path)
        write_markdown(output_dir, module_machine_name, data)
        print(f"Generated: {module_machine_name}.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate markdown documentation from PHP docblocks.")

    parser.add_argument('--target', required=True, help='Base target directory (e.g., /home/user/project).')
    parser.add_argument('--source', help='Path to the base directory containing custom modules. Defaults to <target>/web/modules/custom.')
    parser.add_argument('--output', help='Path to the output directory for markdown files. Defaults to <target>/.docs.')

    args = parser.parse_args()

    # Compute defaults based on target
    source = args.source or os.path.join(args.target, 'web', 'modules', 'custom')
    output = args.output or os.path.join(args.target, 'docs')

    main(source, output)
