# G.CAR.04 Cargo.toml 中依赖包版本不要使用通配符-试行

- **规则ID**：67179966-6c62-4223-aca4-388a7baad2c2
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

依赖的包必须指定具体的语义版本。关于语义版本说明参见: The Cargo book: SemVer Compatibility 。

**【正确示例】**

```
[dependencies]
regex = "1.5"

```
**【错误示例】**

```
[dependencies]
regex = "*"

```
**【修复建议】**
