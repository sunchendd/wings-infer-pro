# SecJ_Empty_While_Stmt

- **规则ID**：6bbda073-1f28-4616-9961-c0a38e32769e
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

不正确的风格

**【正确示例】**

```
public void test01Good(int a, int b) {
    while (a != b) {
        doSomeThing();
    }
}

```
**【错误示例】**

```
public void test01Bad(int a, int b) {
    /* POTENTIAL FLAW: 空while循环块 */
    while (a != b) {
        // empty!
    }
}

```
**【修复建议】**
