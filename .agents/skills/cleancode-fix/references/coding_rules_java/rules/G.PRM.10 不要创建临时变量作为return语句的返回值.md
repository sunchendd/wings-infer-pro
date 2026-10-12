# G.PRM.10 不要创建临时变量作为return语句的返回值

- **规则ID**：67679a87-9f15-48e0-8068-6ce8a13db321
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

不要创建临时变量作为return语句的返回值，保持代码简洁。



工具检查场景:

-检查变量赋值后是否直接被返回。

**【正确示例】**

```
private List<String> func() {
    return solve();
}

```
**【错误示例】**

```
private List<String> func() {
    List<String> res = solve();
    return res;
}

```
**【修复建议】**

去除临时变量和赋值，直接内联到return语句中
