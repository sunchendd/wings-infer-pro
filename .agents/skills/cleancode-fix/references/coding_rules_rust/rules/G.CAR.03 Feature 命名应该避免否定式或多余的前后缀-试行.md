# G.CAR.03 Feature 命名应该避免否定式或多余的前后缀-试行

- **规则ID**：556371c6-51ed-42bb-9862-a45fab38d809
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

Feature 命名应该避免出现 no- 或 not- 之类的否定前缀，或诸如 use-，with- 前缀或 -support后缀。Feature 的目的是正向的，可选的特性，使用否定式命名和它的目的背道而驰。

**【正确示例】**

```
[features]
default = ["abc", "def", "ghi"]
abc = []
def = []
ghi = []

```
**【错误示例】**

```
[features]
default = ["no-abc", "with-def", "ghi-support"]
no-abc = []         # 命名否定式
with-def = []       # 多余前缀
ghi-support = []    # 多余后缀

```
**【修复建议】**
