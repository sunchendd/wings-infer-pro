# G.EXP.03-CPP 使用using定义类型别名

- **规则ID**：9d271b2c-2784-4ff8-9d1f-ea0551207928
- **更新时间**：2025-03-25 19:22:17

---

**【问题级别】**

一般

**【描述】**

类型的别名实际是对类型的封装。而通过封装，可以让代码更清晰，同时在很大程度上避免类型变化带来的散弹式修改。



**【正确示例】**

```
using SomeAlias = std::map<uint32_t, std::vector<int>>;

```
**【错误示例】**

```
typedef std::map<uint32_t, std::vector<int>> SomeAlias;

```
**【修复建议】**

使用using定义别名
