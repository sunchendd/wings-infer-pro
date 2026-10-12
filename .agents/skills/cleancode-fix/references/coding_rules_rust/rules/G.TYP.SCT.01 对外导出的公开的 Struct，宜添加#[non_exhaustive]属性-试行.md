# G.TYP.SCT.01 对外导出的公开的 Struct，宜添加#[non_exhaustive]属性-试行

- **规则ID**：ca8f62b3-2fb9-40cd-9b17-7180a053ed9b
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

作为对外公开的 结构体，为了保持稳定性，应该使用 #[non_exhaustive]属性，避免因为将来结构体字段发生变化而影响到下游的使用。主要涉及命名结构体和元组结构体。

**【正确示例】**

```
// 构建即初始化
let dict = Dictionary::from_file("./words.txt")?;
impl Dictionary {
  fn from_file(filename: impl AsRef<Path>) -> Result<Self, Error> {
    let text = std::fs::read_to_string(filename)?;
    // 不会去存储空状态
    let mut words = Vec::new();
    for line in text.lines() {
      words.push(line);
    }
    Ok(Dictionary { words })
  }
}

```
**【错误示例】**

```
// 先构建
let mut dict = Dictionary::new();
// 后初始化
dict.load_from_file("./words.txt")?;

```
**【修复建议】**
