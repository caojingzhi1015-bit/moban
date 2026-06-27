# 01_jd_parser — 岗位 JD 解析模块

## ① 模块解决的核心痛点
- **图片 JD 无法识别**: 手机截图/拍照 JD，原本只能手动打字录入
- **JD 信息提取残缺**: 职责/要求混在一起，缺少结构化拆分，HR 无法快速匹配
- **AI 编造岗位信息**: 无素材约束时 LLM 自行编造公司名/技能/薪资，产生幻觉

## ② 完整执行业务流水线
```
用户上传 JD (图片/PDF/文本)
  → OcrPdfProcessor 离线解析 (PaddleOCR / MinerU / pdfplumber)
  → 生成带行索引的只读原文素材库
  → 正则预提取硬字段 (年限/学历/薪资/技能关键词)
  → MultiModelGateway AI 结构化抽取 (temperature=0, 专属 JD Schema)
  → 合并结果 (AI 优先，正则兜底)
  → FactCheckValidator 双层校验 (格式正则 + 素材溯源)
  → 输出标准化 JD JSON
```

## ③ 防幻觉 / 防残缺核心机制
- **强Schema约束**: 输出格式固定在 schema.json 中，LLM 无法偏离
- **temperature=0**: 关闭模型随机性发散，确保提取一致性
- **正则兜底**: 即使 AI 失败，正则也能提取年限/学历/技能关键词，不丢数据
- **source_index 绑定**: 每条职责/要求标注原文行号，可溯源验证真伪
- **双层校验**: 格式正则检查 + 素材溯源检查，拦截编造内容
- **全局防幻觉 Prompt**: 每次 AI 调用自动前置拼接，切换模型也不丢失约束

## ④ 与其他模块的数据互通逻辑
- **输出给 03_info_enquiry_agent**: JD 技能关键词 → 识别简历中缺失的能力 → 生成追问
- **输出给 04_target_resume_generator**: JD 匹配权重关键词 → 经历按 JD 匹配度排序
- **输出给 05_ai_interviewer**: 岗位信息 → 面试官据此提问
- **输入来自 common/ocr_pdf_processor**: 图片/PDF 解析为可读文本
- **输入来自 common/multi_model_gateway**: 所有 AI 调用统一经过网关
