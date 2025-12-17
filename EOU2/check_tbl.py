import re
import os
import sys

def read_file_with_fallback(file_path):
    """尝试用不同编码读取文件"""
    encodings_to_try = [
        'utf-8-sig',  # UTF-8 with BOM
        'utf-8',      # UTF-8 without BOM
        'gbk',        # 简体中文
        'gb2312',     # 简体中文
        'big5',       # 繁体中文
        'shift_jis',  # 日文
        'euc-jp',     # 日文
        'cp932',      # 日文 Windows
        'latin-1',    # 西欧语言
        'cp1252',     # Windows Latin-1
    ]
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            print(f"成功用 {encoding} 编码读取文件")
            return content, encoding
        except UnicodeDecodeError:
            continue
    
    # 如果所有编码都失败，尝试用二进制读取
    try:
        with open(file_path, 'rb') as f:
            content_bytes = f.read()
        
        # 尝试解码为字符串（忽略错误）
        for encoding in encodings_to_try:
            try:
                content = content_bytes.decode(encoding, errors='ignore')
                print(f"用 {encoding} 编码读取文件（忽略错误字符）")
                return content, encoding
            except:
                continue
        
        # 最后尝试用替换错误字符的方式
        content = content_bytes.decode('utf-8', errors='replace')
        return content, 'utf-8 (with replacement)'
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None, None

def extract_full_entry(lines, start_idx):
    """提取完整的PO条目"""
    entry_lines = []
    i = start_idx
    
    while i < len(lines):
        line = lines[i].rstrip('\n\r')
        entry_lines.append(line)
        
        # 如果遇到空行，结束当前条目
        if not line.strip():
            i += 1
            # 跳过连续的空行
            while i < len(lines) and not lines[i].strip():
                i += 1
            break
        i += 1
    
    return entry_lines, i

def find_quote_problems(text):
    """查找文本中的引号问题"""
    problems = []
    
    # 检查未闭合的引号
    in_quote = False
    escape_next = False
    
    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"':
            if in_quote:
                in_quote = False
            else:
                in_quote = True
    
    if in_quote:
        problems.append("存在未闭合的引号")
    
    # 检查是否有单独的引号（不是成对出现）
    clean_text = text.replace('\\"', '')
    quote_count = clean_text.count('"')
    if quote_count % 2 != 0:
        problems.append(f"引号数量为奇数({quote_count})，可能不成对")
    
    # 检查是否有未转义的引号
    # 查找所有不在转义序列中的引号
    for i in range(len(text)):
        if text[i] == '"':
            # 检查前面是否有转义符
            if i == 0 or text[i-1] != '\\':
                # 检查是否在字符串边界
                problems.append(f"位置{i}: 可能未转义的引号")
    
    return problems

def validate_po_file(file_path):
    """验证单个PO文件的格式"""
    
    if not os.path.exists(file_path):
        print(f"错误: 文件 '{file_path}' 不存在")
        return False
    
    if not os.path.isfile(file_path):
        print(f"错误: '{file_path}' 不是文件")
        return False
    
    # 读取文件
    content, encoding = read_file_with_fallback(file_path)
    if content is None:
        return False
    
    errors = []
    warnings = []
    problem_entries = []  # 存储有问题的条目
    
    lines = content.split('\n')
    i = 0
    entry_num = 0
    
    while i < len(lines):
        # 跳过空行
        if not lines[i].strip():
            i += 1
            continue
        
        entry_num += 1
        entry_lines, next_i = extract_full_entry(lines, i)
        i = next_i
        
        if not entry_lines:
            continue
        
        current_entry = {
            'entry_num': entry_num,
            'lines': entry_lines,
            'msgid': '',
            'msgstr': '',
            'has_msgid': False,
            'has_msgstr': False,
            'errors': [],
            'context': None
        }
        
        # 分析条目
        for line_num, line in enumerate(entry_lines, 1):
            line = line.rstrip('\n\r')
            
            # 跳过空行和注释
            if not line.strip():
                continue
            
            # 检查msgctxt
            if line.lstrip().startswith('msgctxt'):
                current_entry['context'] = line.strip()
            
            # 检查msgid
            elif line.lstrip().startswith('msgid'):
                current_entry['has_msgid'] = True
                msgid_line = line.strip()
                
                # 提取msgid值
                if msgid_line.startswith('msgid "'):
                    # 提取引号内的内容
                    match = re.search(r'msgid "(.*)"$', msgid_line)
                    if match:
                        current_entry['msgid'] = match.group(1)
                    else:
                        # 可能是多行msgid
                        current_entry['msgid'] = msgid_line[6:]  # 去掉'msgid '
                else:
                    current_entry['errors'].append(f"行{line_num}: msgid缺少起始引号")
                
                # 检查msgid格式
                if not line.lstrip().startswith('msgid "'):
                    current_entry['errors'].append(f"行{line_num}: msgid格式错误 - 应以'msgid \"'开头")
                
                # 检查引号
                if '"' not in line:
                    current_entry['errors'].append(f"行{line_num}: msgid缺少引号")
                else:
                    # 检查引号问题
                    quote_problems = find_quote_problems(current_entry['msgid'])
                    for problem in quote_problems:
                        current_entry['errors'].append(f"行{line_num}: msgid引号问题 - {problem}")
            
            # 检查msgstr
            elif line.lstrip().startswith('msgstr'):
                current_entry['has_msgstr'] = True
                msgstr_line = line.strip()
                
                # 提取msgstr值
                if msgstr_line.startswith('msgstr "'):
                    # 提取引号内的内容
                    match = re.search(r'msgstr "(.*)"$', msgstr_line)
                    if match:
                        current_entry['msgstr'] = match.group(1)
                    else:
                        # 可能是多行msgstr
                        current_entry['msgstr'] = msgstr_line[8:]  # 去掉'msgstr '
                else:
                    current_entry['errors'].append(f"行{line_num}: msgstr缺少起始引号")
                
                # 检查msgstr格式
                if not line.lstrip().startswith('msgstr "'):
                    current_entry['errors'].append(f"行{line_num}: msgstr格式错误 - 应以'msgstr \"'开头")
                
                # 检查引号
                if '"' not in line:
                    current_entry['errors'].append(f"行{line_num}: msgstr缺少引号")
                else:
                    # 检查引号问题
                    quote_problems = find_quote_problems(current_entry['msgstr'])
                    for problem in quote_problems:
                        current_entry['errors'].append(f"行{line_num}: msgstr引号问题 - {problem}")
            
            # 检查多行字符串
            elif line.lstrip().startswith('"'):
                # 检查字符串行格式
                if not line.endswith('"'):
                    # 检查下一行是否也是字符串行
                    next_line_idx = line_num
                    if next_line_idx < len(entry_lines):
                        next_line = entry_lines[next_line_idx].rstrip('\n\r')
                        if not next_line.lstrip().startswith('"'):
                            current_entry['errors'].append(f"行{line_num}: 字符串行缺少结束引号")
        
        # 验证条目完整性
        if not current_entry['has_msgid']:
            current_entry['errors'].append("缺少msgid定义")
        
        if not current_entry['has_msgstr']:
            current_entry['errors'].append("缺少msgstr定义")
        
        # 如果有错误，添加到问题条目列表
        if current_entry['errors']:
            problem_entries.append(current_entry)
    
    # 输出结果
    print(f"检查文件: {file_path}")
    print(f"文件编码: {encoding}")
    print(f"总条目数: {entry_num}")
    print(f"问题条目数: {len(problem_entries)}")
    print("=" * 80)
    
    if problem_entries:
        print("❌ 发现以下有问题的条目:\n")
        
        for entry in problem_entries:
            print(f"【条目 #{entry['entry_num']}】")
            print("-" * 40)
            
            # 显示上下文
            if entry['context']:
                print(f"上下文: {entry['context']}")
            
            # 显示msgid
            if entry['msgid']:
                print(f"原文(msgid): \"{entry['msgid']}\"")
            elif entry['has_msgid']:
                print("原文(msgid): (空)")
            
            # 显示msgstr
            if entry['msgstr']:
                print(f"译文(msgstr): \"{entry['msgstr']}\"")
            elif entry['has_msgstr']:
                print("译文(msgstr): (空)")
            
            # 显示错误
            print("\n发现的问题:")
            for error in entry['errors']:
                print(f"  • {error}")
            
            # 显示原始文本
            print("\n原始文本:")
            for j, line in enumerate(entry['lines'], 1):
                line_num_str = str(j).rjust(3)
                print(f"{line_num_str}: {repr(line)[1:-1] if line else '(空行)'}")
            
            print("\n" + "=" * 80 + "\n")
        
        return False
    else:
        print("✅ 所有条目格式正确！")
        return True

def main():
    if len(sys.argv) != 2:
        print("PO文件格式检查工具")
        print("=" * 50)
        print("用法: python check_po.py <po文件路径>")
        print("示例: python check_po.py translation.po")
        print("示例: python check_po.py \"D:\\我的文件\\translation.po\"")
        print()
        print("检查内容包括:")
        print("  1. msgid和msgstr的引号格式")
        print("  2. 字符串行的引号闭合")
        print("  3. 转义引号的处理")
        print("  4. 条目完整性")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"错误: 文件 '{file_path}' 不存在")
        sys.exit(1)
    
    if not os.path.isfile(file_path):
        print(f"错误: '{file_path}' 不是文件")
        sys.exit(1)
    
    is_valid = validate_po_file(file_path)
    
    if is_valid:
        print("\n✅ 文件格式有效")
        sys.exit(0)
    else:
        print("\n❌ 文件格式有问题需要修复")
        sys.exit(1)

if __name__ == "__main__":
    main()