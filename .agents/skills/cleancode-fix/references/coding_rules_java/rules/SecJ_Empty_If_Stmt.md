# SecJ_Empty_If_Stmt

- **规则ID**：1ed718fb-7335-4674-b101-7f48bf562c90
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

不正确的风格

**【正确示例】**

```
public void test01Good(int x) {
    if (x == 0) {
        doSomeThing();
    }
}

```
**【错误示例】**

```
public void test01Bad(int x) {
    /* POTENTIAL FLAW: 空If语句块 */
    if (x == 0) {
        // empty!
    }
}

```
**【修复建议】**
