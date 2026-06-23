"""文本标准化工具 — Python 移植自 extraction-pipeline.js"""
import re


def normalize_text(text: str) -> str:
    """标准化文本：统一换行、折叠空白、括号标准化"""
    if not text:
        return ""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 折叠连续空白行（保留最多1个空行）
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 折叠行内多空格
    text = re.sub(r'[ \t]{3,}', '  ', text)
    # 全角括号标准化
    text = text.replace('（', '(').replace('）', ')')
    text = text.replace('【', '[').replace('】', ']')
    return text.strip()


def extract_section(text: str, keywords: list[str]) -> str:
    """从文本中提取关键词对应的章节内容"""
    if not text or not keywords:
        return ""

    lines = text.split('\n')
    start_idx = -1
    keyword_pattern = '|'.join(re.escape(kw) for kw in keywords)

    # 找到起始行
    for i, line in enumerate(lines):
        if re.search(keyword_pattern, line, re.IGNORECASE):
            start_idx = i
            break

    if start_idx == -1:
        return ""

    # 找到下一个章节标题作为结束
    # 注意：这些模式应该是章节标题，不能匹配正文中的普通词汇
    # 使用更严格的规则：行首匹配 或 行短且无内容
    section_header_keywords = [
        r'教育经历', r'教育背景', r'学历背景', r'学习经历',
        r'工作经历', r'工作经验', r'实习经历', r'工作履历', r'职业经历', r'从业经历',
        r'项目经历', r'项目经验',
        r'技能', r'专业技能', r'技能证书', r'技术栈', r'证书',
        r'自我评价', r'自我介绍', r'个人评价', r'自我描述',
        r'基本信息', r'个人信息', r'个人资料',
        r'求职意向', r'期望岗位', r'期望职位', r'目标岗位',
        r'Education', r'Work Experience', r'Projects', r'Skills', r'Certificates',
    ]
    end_pattern = '|'.join(section_header_keywords)

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        # 跳过当前关键词匹配到的行
        if re.search(keyword_pattern, line, re.IGNORECASE):
            continue
        # 严格匹配：行首匹配 或 短行(<25字)且匹配
        if re.search(end_pattern, line, re.IGNORECASE):
            stripped = line.strip()
            # 是章节标题的条件：行很短（<25字）或关键词在行首
            if len(stripped) < 25 or re.match(end_pattern, stripped, re.IGNORECASE):
                end_idx = i
                break

    section_lines = lines[start_idx:end_idx]
    return '\n'.join(section_lines).strip()


def extract_date_range(text: str) -> dict | None:
    """从文本中提取日期范围"""
    patterns = [
        # 2020.01 - 2022.12 或 2020年1月 - 至今
        r'(?P<start>\d{4}[.\-/年]\d{1,2})[月]?\s*[-–—~至到]\s*(?P<end>\d{4}[.\-/年]\d{1,2}[月]?|至今|现在|present|Now|Present)',
        # 2020 - 2022
        r'(?P<start>\d{4})\s*[-–—~至到]\s*(?P<end>\d{4}|至今|现在|present)',
        # 2020.01-2022.12 (compact)
        r'(?P<start>\d{4}\.\d{1,2})-(?P<end>\d{4}\.\d{1,2}|至今|现在|present)',
        # 2020/01-2022/12
        r'(?P<start>\d{4}/\d{1,2})-(?P<end>\d{4}/\d{1,2}|至今|现在|present)',
    ]

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            start = m.group('start').strip()
            end = m.group('end').strip()
            # 标准化
            start = start.replace('年', '-').replace('月', '').replace('/', '-').replace('.', '-')
            end = end.replace('年', '-').replace('月', '').replace('/', '-').replace('.', '-')
            if end in ('至今', '现在', 'present', 'Present', 'Now'):
                end = '至今'
            return {'start': start, 'end': end}

    return None


def extract_city(text: str) -> str | None:
    """提取城市名"""
    cities = [
        '北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '南京',
        '西安', '重庆', '苏州', '天津', '长沙', '郑州', '东莞', '青岛',
        '厦门', '合肥', '佛山', '宁波', '昆明', '沈阳', '大连', '福州',
        '无锡', '济南', '常州', '温州', '石家庄', '哈尔滨', '南昌', '南宁',
        '贵阳', '太原', '兰州', '海口', '乌鲁木齐', '呼和浩特', '银川',
    ]

    # 先尝试标签匹配
    m = re.search(r'(?:城市|所在地|Base|Location|现居|所在城市|居住地)[：:\s]*([^\n,，。]{2,10})', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 然后尝试城市名直接匹配（优先匹配较长的城市名）
    for city in sorted(cities, key=len, reverse=True):
        if city in text:
            return city

    return None


def find_tech_stack(text: str) -> list[str]:
    """从文本中检测技术栈"""
    tech_patterns = [
        r'Python', r'Java\b', r'JavaScript', r'TypeScript', r'React', r'Vue', r'Angular',
        r'Node\.?js', r'Go(lang)?', r'Rust', r'C\+\+', r'SQL', r'MySQL', r'PostgreSQL',
        r'MongoDB', r'Redis', r'Docker', r'Kubernetes', r'K8s', r'AWS', r'Azure', r'GCP',
        r'TensorFlow', r'PyTorch', r'Machine\s*Learning', r'Deep\s*Learning', r'NLP', r'LLM',
        r'Excel', r'Tableau', r'Power\s*BI', r'Spark', r'Hadoop', r'Flink',
        r'Figma', r'Sketch', r'Photoshop', r'Illustrator', r'After\s*Effects', r'Canva',
        r'Linux', r'Git', r'CI/CD', r'Jenkins', r'Terraform', r'Ansible',
        r'Spring\s*Boot', r'Django', r'Flask', r'FastAPI', r'Express', r'Next\.?js',
        r'GraphQL', r'REST', r'gRPC', r'WebSocket',
    ]

    found = []
    for pat in tech_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m and m.group(0) not in found:
            found.append(m.group(0))
    return found
