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
                params.append(f"{param_name} ({param_type}): {param_desc}")
            else:
                params.append(full_text)
        elif current_tag == '@return':
            full_text = " ".join(current_tag_content).strip()
            match = re.match(r'@return\s+(\S+)\s*(.*)', full_text)
            if match:
                return_type, return_desc = match.groups()
                returns = f"{return_type}: {return_desc}"
            else:
                returns = full_text
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
            else:
                if not current_tag:
                    description_lines.append(stripped)

    if current_tag:
        flush_current_tag()

    return {
        'description': " ".join(description_lines).strip(),
        'params': params,
        'returns': returns
    }


def extract_php_class_docblocks(file_content):
    class_pattern = re.compile(
        r"/\*\*(.*?)\*/\s*(?:abstract\s+)?(?:final\s+)?class\s+(\w+)\s*(?:extends\s+\w+)?\s*\{",
        re.DOTALL | re.MULTILINE
    )

    method_pattern = re.compile(
        r"/\*\*(.*?)\*/\s*(public|protected|private)?\s*(static\s+)?function\s+(\w+)\s*\(([^)]*)\)",
        re.DOTALL | re.MULTILINE
    )

    classes = []

    for class_match in class_pattern.finditer(file_content):
        class_doc, class_name = class_match.groups()
        class_clean = clean_docblock(class_doc)

        class_start = class_match.end()
        brace_count = 1
        index = class_start
        while brace_count > 0 and index < len(file_content):
            if file_content[index] == '{':
                brace_count += 1
            elif file_content[index] == '}':
                brace_count -= 1
            index += 1

        class_body = file_content[class_start:index]

        methods = []
        for method_match in method_pattern.finditer(class_body):
            method_doc, visibility, static_kw, method_name, _ = method_match.groups()
            method_clean = clean_docblock(method_doc)

            methods.append({
                'name': method_name,
                'visibility': visibility or 'public',
                'description': method_clean['description'],
                'params': method_clean['params'],
                'returns': method_clean['returns']
            })

        classes.append({
            'name': class_name,
            'description': class_clean['description'],
            'methods': methods
        })

    return classes


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
                    classes = extract_php_class_docblocks(content)
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

    def anchor(text):
        return slugify(text)

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
                cls_anchor = slugify(cls['name'])
                f.write(f"- [{cls['name']}](#{cls_anchor})\n")
                if cls['methods']:
                    for method in cls['methods']:
                        method_anchor = slugify(method['name'], is_method=True)
                        full_anchor = f"{cls_anchor}__{method_anchor}"
                        f.write(f"  - [{method['name']}()](#{full_anchor})\n")
            f.write("\n")

            # Classes & Collapsible Method Sections
            f.write("## Classes\n\n")
            for cls in data['classes']:
                cls_anchor = slugify(cls['name'])
                f.write(f"### {cls['name']}\n\n")
                f.write(f"{cls['description']}\n\n")

                if cls['methods']:
                    # Start collapsible section
                    f.write("<details>\n")
                    f.write(f"<summary>Show Methods</summary>\n\n")

                    for method in cls['methods']:
                        method_anchor = slugify(method['name'], is_method=True)
                        full_anchor = f"{cls_anchor}__{method_anchor}"

                        f.write(f'<a id="{full_anchor}"></a>\n')
                        f.write(f"##### {method['name']}()\n\n")
                        f.write(f"- **Visibility:** {method['visibility']}\n")
                        f.write(f"- **Description:** {method['description']}\n")

                        if method['params']:
                            f.write(f"- **Parameters:**\n")
                            for p in method['params']:
                                f.write(f"  - {p}\n")

                        if method['returns']:
                            f.write(f"- **Returns:** {method['returns']}\n")

                        f.write("\n---\n\n")

                    # End collapsible section
                    f.write("</details>\n\n")

                else:
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
    output = args.output or os.path.join(args.target, '.docs')

    main(source, output)
