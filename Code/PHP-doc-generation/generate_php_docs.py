import os
import re
import yaml
import argparse
import shutil


def extract_info_yml(path):
    """Extract module info from .info.yml files (Drupal specific)"""
    if not os.path.exists(path):
        return None

    with open(path, 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)
        return {
            'name': info.get('name', os.path.basename(path)),
            'description': info.get('description', 'No description provided.')
        }


def clean_docblock(docblock: str):
    """Parse a PHPDoc block and extract description, parameters, returns, and properties while preserving formatting."""
    if not docblock:
        return {
            'description': '',
            'params': [],
            'returns': None,
            'properties': [],
            'annotations': []
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

    # Now process the rest of the docblock while preserving formatting
    lines = [line.rstrip() for line in docblock.strip().splitlines()]
    description_lines = []
    params = []
    returns = None
    annotations = []

    current_tag = None
    current_tag_content = []

    def flush_current_tag():
        nonlocal current_tag, current_tag_content, params, returns, annotations
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
        elif current_tag and current_tag.startswith('@'):
            # Handle other annotations (like Drupal's @Block, @Translation, etc.)
            full_text = " ".join(current_tag_content).strip()
            annotations.append(full_text)

        current_tag = None
        current_tag_content = []

    for line in lines:
        stripped = line.lstrip(" *")
        original_stripped = line.replace(' * ', '', 1).strip()  # Preserve original formatting

        # Check for any tag starting with @
        tag_match = re.match(r'@(\w+)', stripped)
        if tag_match:
            if current_tag:
                flush_current_tag()
            current_tag = stripped.split()[0]  # Get the full tag including @
            current_tag_content = [stripped]
        elif stripped.startswith('@'):
            if current_tag:
                flush_current_tag()
            current_tag = None
            current_tag_content = []
        else:
            if current_tag and stripped != '':
                current_tag_content.append(stripped)
            elif not current_tag and original_stripped != '':
                # Preserve the original line formatting for description
                description_lines.append(original_stripped)

    if current_tag:
        flush_current_tag()

    # Clean up description while preserving structure
    description = "\n".join(description_lines).strip()

    # Remove excessive empty lines but preserve basic structure
    description = re.sub(r'\n\s*\n\s*\n+', '\n\n', description)

    # Clean up any remaining asterisks or docblock artifacts
    description = re.sub(r'^\s*\*\s*', '', description, flags=re.MULTILINE)

    return {
        'description': description,
        'params': params,
        'returns': returns,
        'properties': properties,
        'annotations': annotations
    }


def extract_php_definitions(file_content):
    """
    Extracts classes, interfaces, traits, and enums with docblocks, attributes and properties.
    """
    # Pattern to match PHP 8 attributes (including Symfony and Doctrine)
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

    # Pattern to match Symfony Route annotations
    route_pattern = re.compile(
        r'#\[Route\(([^)]+)\)\]',
        re.DOTALL | re.MULTILINE
    )

    definitions = []

    for match in definition_pattern.finditer(file_content):
        docblock, def_type, name, enum_type = match.groups()
        clean_doc = clean_docblock(docblock) if docblock else {'description': '_No description available._', 'annotations': []}

        # Extract attributes before the definition
        def_start = match.start()
        preceding_text = file_content[max(0, def_start-500):def_start]
        attributes = []

        # Extract all attributes
        for attr_match in attribute_pattern.finditer(preceding_text):
            attr_name = attr_match.group(1).split('\\')[-1]
            attr_params = attr_match.group(2) or ''

            # Special handling for Route attributes
            if attr_name == 'Route':
                route_matches = route_pattern.findall(preceding_text)
                for route_match in route_matches:
                    attributes.append({
                        'name': 'Route',
                        'params': route_match.strip(),
                        'type': 'symfony'
                    })
            else:
                # Handle Doctrine and other attributes
                attributes.append({
                    'name': attr_name,
                    'params': attr_params,
                    'type': 'doctrine' if 'ORM' in attr_match.group(1) else 'general'
                })

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
            method_clean = clean_docblock(method_doc) if method_doc else {'description': '', 'annotations': []}

            # Get method attributes
            method_start = method_match.start()
            method_preceding = body[max(0, method_start-200):method_start]
            method_attributes = []

            for attr_match in attribute_pattern.finditer(method_preceding):
                attr_name = attr_match.group(1).split('\\')[-1]
                attr_params = attr_match.group(2) or ''

                if attr_name == 'Route':
                    route_matches = route_pattern.findall(method_preceding)
                    for route_match in route_matches:
                        method_attributes.append({
                            'name': 'Route',
                            'params': route_match.strip(),
                            'type': 'symfony'
                        })
                else:
                    method_attributes.append({
                        'name': attr_name,
                        'params': attr_params,
                        'type': 'doctrine' if 'ORM' in attr_match.group(1) else 'general'
                    })

            methods.append({
                'name': method_name,
                'visibility': visibility or 'public',
                'description': method_clean.get('description', ''),
                'params': method_clean.get('params', []),
                'returns': method_clean.get('returns'),
                'attributes': method_attributes,
                'static': bool(static_kw),
                'annotations': method_clean.get('annotations', [])
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

        # Parse properties with their attributes
        properties = clean_doc.get('properties', [])

        # Add properties from inline docblocks with attributes
        for prop_match in property_pattern.finditer(body):
            prop_doc = prop_match.group(1)
            prop_type = prop_match.group(2)
            prop_name = prop_match.group(3)

            # Extract property attributes
            prop_start = prop_match.start()
            prop_preceding = body[max(0, prop_start-200):prop_start]
            prop_attributes = []

            for attr_match in attribute_pattern.finditer(prop_preceding):
                attr_name = attr_match.group(1).split('\\')[-1]
                attr_params = attr_match.group(2) or ''

                prop_attributes.append({
                    'name': attr_name,
                    'params': attr_params,
                    'type': 'doctrine' if 'ORM' in attr_match.group(1) else ('symfony' if 'Groups' in attr_name else 'general')
                })

            properties.append({
                'name': prop_name,
                'type': prop_type,
                'description': clean_docblock(prop_doc)['description'] if prop_doc else '',
                'attributes': prop_attributes
            })

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
        for hint_match in type_hint_pattern.finditer(body):
            prop_name = hint_match.group(2)
            if prop_name not in documented_props:
                # Extract attributes for type-hinted properties
                prop_start = hint_match.start()
                prop_preceding = body[max(0, prop_start-200):prop_start]
                prop_attributes = []

                for attr_match in attribute_pattern.finditer(prop_preceding):
                    attr_name = attr_match.group(1).split('\\')[-1]
                    attr_params = attr_match.group(2) or ''

                    prop_attributes.append({
                        'name': attr_name,
                        'params': attr_params,
                        'type': 'doctrine' if 'ORM' in attr_match.group(1) else ('symfony' if 'Groups' in attr_name else 'general')
                    })

                properties.append({
                    'name': prop_name,
                    'type': hint_match.group(1),
                    'description': 'No description available',
                    'attributes': prop_attributes
                })

        # Build definition
        definition = {
            'type': def_type,
            'name': name,
            'description': clean_doc['description'],
            'methods': methods,
            'properties': properties,
            'attributes': attributes,
            'annotations': clean_doc.get('annotations', [])
        }

        if def_type == 'enum':
            definition.update({
                'enum_type': enum_type or 'string',
                'cases': cases
            })

        definitions.append(definition)

    return definitions


def scan_directory(directory_path, is_drupal=False):
    """Scan a directory for PHP files and extract definitions."""
    result = {
        'classes': [],
        'files': {}
    }

    if is_drupal:
        # Drupal-specific: look for .info.yml files
        info_yml = None
        for file in os.listdir(directory_path):
            if file.endswith('.info.yml'):
                info_yml = os.path.join(directory_path, file)
                break

        if info_yml:
            result['metadata'] = extract_info_yml(info_yml)
        else:
            result['metadata'] = {
                'name': os.path.basename(directory_path),
                'description': 'No module info found.'
            }
    else:
        # Non-Drupal: use directory name as module name
        result['metadata'] = {
            'name': os.path.basename(directory_path),
            'description': 'Project component'
        }

    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(('.php', '.module', '.install')):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, directory_path)

                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    classes = extract_php_definitions(content)

                    if classes:
                        result['files'][relative_path] = classes
                        result['classes'].extend(classes)

    # Extract README if it exists in this specific directory
    readme = extract_readme(directory_path)
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


def generate_filename_from_path(relative_path):
    """Generate a filename from a relative path like Controller/Admin/UserController.php"""
    # Remove file extension
    name = os.path.splitext(relative_path)[0]
    # Replace slashes and backslashes with hyphens
    name = name.replace('/', '-').replace('\\', '-')
    # Remove any remaining special characters
    name = re.sub(r'[^a-zA-Z0-9\-]', '', name)
    # Convert to lowercase
    return name.lower() + '.md'


def write_markdown(output_dir, filename, data, file_path=None):
    """Write markdown documentation for a file or directory."""
    output_path = os.path.join(output_dir, filename)

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

    with open(output_path, 'w', encoding='utf-8') as f:
        # Title
        if file_path:
            f.write(f"# {os.path.basename(file_path)}\n\n")
            f.write(f"**File:** `{file_path}`\n\n")
        else:
            f.write(f"# {data['metadata']['name']}\n\n")

        # Overview or Description
        if data.get('readme'):
            f.write("## Overview\n\n")
            f.write(data['readme'] + "\n\n")
        elif data['metadata'].get('description'):
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

                # Display description with preserved formatting
                if cls['description']:
                    f.write(f"{cls['description']}\n\n")

                # Display Drupal-style annotations
                if cls.get('annotations'):
                    f.write("#### Annotations\n\n")
                    for annotation in cls['annotations']:
                        f.write(f"`{annotation}`  \n")
                    f.write("\n")

                # Display class-level attributes
                if cls.get('attributes'):
                    f.write("#### Attributes\n\n")
                    for attr in cls['attributes']:
                        if attr['type'] == 'symfony':
                            f.write(f"- **Symfony Route:** `#[Route({attr['params']})]`\n")
                        elif attr['type'] == 'doctrine':
                            f.write(f"- **Doctrine ORM:** `#[{attr['name']}({attr['params']})]`\n")
                        else:
                            f.write(f"- `#[{attr['name']}({attr['params']})]`\n")
                    f.write("\n")

                # Display properties with their attributes
                if cls.get('properties'):
                    f.write("#### Properties\n\n")
                    f.write("| Name | Type | Description | Attributes |\n")
                    f.write("|------|------|-------------|------------|\n")
                    for prop in cls['properties']:
                        prop_anchor = f"{cls_anchor}__property-{anchor(prop['name'])}"
                        name_display = f"${prop['name']}"

                        # Format attributes for display
                        attr_display = []
                        for attr in prop.get('attributes', []):
                            if attr['type'] == 'doctrine':
                                attr_display.append(f"ORM:{attr['name']}")
                            elif attr['type'] == 'symfony':
                                attr_display.append(f"Symfony:{attr['name']}")
                            else:
                                attr_display.append(attr['name'])

                        attr_str = ", ".join(attr_display) if attr_display else "—"

                        f.write(f"| <a id='{prop_anchor}'></a>{name_display} | `{prop['type']}` | {prop['description']} | `{attr_str}` |\n")
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

                        # Display method attributes
                        if method.get('attributes'):
                            f.write("- **Attributes:**\n")
                            for attr in method['attributes']:
                                if attr['type'] == 'symfony':
                                    f.write(f"  - `#[Route({attr['params']})]`\n")
                                else:
                                    f.write(f"  - `#[{attr['name']}({attr['params']})]`\n")

                        # Display method annotations
                        if method.get('annotations'):
                            f.write("- **Annotations:**\n")
                            for annotation in method['annotations']:
                                f.write(f"  - `{annotation}`\n")

                        # Display method description with preserved formatting
                        if method['description']:
                            f.write(f"- **Description:**\n{method['description']}\n")

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


def copy_project_readme(target_dir, output_dir):
    """Copy from main project README.md and create overview.md"""
    main_readme = os.path.join(target_dir, 'README.md')
    if os.path.exists(main_readme):
        # Create overview.md with the content (without the main title)
        with open(main_readme, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines and lines[0].startswith('# '):
                lines = lines[1:]
            content = ''.join(lines).strip()

        with open(os.path.join(output_dir, 'overview.md'), 'w', encoding='utf-8') as f:
            f.write("# Project Overview\n\n")
            f.write(content + "\n")

        print("Copied project README and created overview.md")


def main(target_dir, source_subdir, output_subdir, is_drupal=False):
    source_dir = os.path.join(target_dir, source_subdir)

    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist")
        exit(1)

    if not os.path.exists(output_subdir):
        os.makedirs(output_subdir)

    # Copy project README if it exists
    copy_project_readme(target_dir, output_subdir)

    # For Drupal, scan each module directory
    if is_drupal:
        for module in os.listdir(source_dir):
            module_path = os.path.join(source_dir, module)
            if not os.path.isdir(module_path):
                continue

            data = scan_directory(module_path, is_drupal=True)
            if not data or not data['classes']:
                continue

            filename = f"{module}.md"
            write_markdown(output_subdir, filename, data)
            print(f"Generated: {filename}")

    else:
        # For non-Drupal, scan the entire source directory and create files by path
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith(('.php', '.module', '.install')):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, source_dir)

                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        classes = extract_php_definitions(content)

                        if classes:
                            data = {
                                'metadata': {
                                    'name': os.path.basename(file),
                                    'description': f'File: {relative_path}'
                                },
                                'classes': classes
                            }

                            filename = generate_filename_from_path(relative_path)
                            write_markdown(output_subdir, filename, data, file_path=relative_path)
                            print(f"Generated: {filename} (from {relative_path})")

            # Also scan each subdirectory for README and classes
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                data = scan_directory(dir_path, is_drupal=False)

                if data['classes']:
                    relative_dir = os.path.relpath(dir_path, source_dir)
                    filename = generate_filename_from_path(relative_dir) if relative_dir != '.' else 'index.md'
                    write_markdown(output_subdir, filename, data)
                    print(f"Generated: {filename} (from directory {relative_dir})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate markdown documentation from PHP docblocks.")

    parser.add_argument('--target', required=True, help='Absolute path to the project root directory.')
    parser.add_argument('--source', required=True, help='Subdirectory within target to scan (e.g., web/modules/custom, src).')
    parser.add_argument('--output', help='Path to the output directory for markdown files. Defaults to <target>/docs.')
    parser.add_argument('--drupal', action='store_true', help='Use Drupal mode (module-based structure).')

    args = parser.parse_args()

    output_dir = args.output or os.path.join(args.target, 'docs')

    # Validate target directory exists
    if not os.path.exists(args.target):
        print(f"Error: Target directory '{args.target}' does not exist")
        exit(1)

    main(args.target, args.source, output_dir, args.drupal)
