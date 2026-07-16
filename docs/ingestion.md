# 原始 Prompt 导入与清洗

第 4 步建立从外部原始文件到待标注标准数据的转换流程。

## 数据边界

```text
CSV / JSONL 原始数据
        ↓
RawPromptInput
        ↓
确定性文本清洗
        ↓
长度和字段校验
        ↓
IngestedPromptRecord
        ↓
待后续去重与分类
```

`RawPromptInput` 不可信，字段可能缺失、格式可能错误、文本可能包含不可见字符。
`IngestedPromptRecord` 已完成基础清洗，但没有分类标签，不能直接作为金标准数据。

## 原始文件字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `external_id` | 是 | 来源系统中的记录 ID |
| `prompt_text` | 是 | 未清洗 Prompt |
| `source_type` | 是 | synthetic、public_web、internal 或 manual |
| `source_reference` | 否 | 来源链接或内部编号 |
| `language` | 否 | 默认 zh-CN |
| `scope` | 否 | 默认 creative_writing |

## 清洗规则

当前只执行不会主动改变语义的确定性操作：

1. 统一 Windows、旧 Mac 和 Unix 换行符；
2. 使用 Unicode NFC 统一等价编码，并定向转换全角字母、数字和全角空格；
3. 删除常见零宽字符和 BOM；
4. 删除换行、制表符以外的控制字符；
5. 合并连续水平空白及三个以上连续换行；
6. 去除每行首尾空白和全文首尾空白。

当前不会执行分词、纠错、敏感词替换、HTML 标签删除或模型改写，因为这些操作可能改变 Prompt 原意。
中文全角标点也会保留，不使用可能改变表达形式的通用 NFKC 兼容转换。

## 错误处理

- 单行失败不会中断整个文件；
- 错误保留原始行号和 external_id；
- 合法记录仍会输出；
- 只要存在拒绝记录，CLI 返回退出码 1；
- 文件不存在、格式不支持或参数错误返回退出码 2。

## 运行

```bash
creativebench-import data/examples/raw_prompts.csv
```

默认输出到 `data/processed/imported_prompts.jsonl`。该目录属于生成数据，已被 Git 忽略。
