# G.CNS.04 不应在常量定义中增加显式的 'static 生命周期-试行

- **规则ID**：bba38190-2a30-4641-a34d-356e4a405858
- **更新时间**：2025-06-05 04:40:01

---

**【问题级别】**

一般

**【描述】**

在常量和静态变量声明时已经默认含有隐式的'static生命周期，所以不需要额外增加显式'static声明周期。

**【正确示例】**

```
const FOO: &[(&str, &str, fn(&Bar) -> bool)] = &[...]
 static FOO: &[(&str, &str, fn(&Bar) -> bool)] = &[...]

```
**【错误示例】**

```
const FOO: &'static [(&'static str, &'static str, fn(&Bar) -> bool)] =
&[...]
static FOO: &'static [(&'static str, &'static str, fn(&Bar) -> bool)] =
&[...]

```
**【修复建议】**
