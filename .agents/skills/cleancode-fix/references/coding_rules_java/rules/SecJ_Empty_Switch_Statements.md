# SecJ_Empty_Switch_Statements

- **规则ID**：559af44f-9b6b-4ebb-a9f7-2b8c57660de8
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

不正确的风格

**【正确示例】**

```
public void test01Good() {
    int x = 2;
    switch (x) {
        doSomeThing();
    }
}

```
**【错误示例】**

```
public void test01Bad() {
    int x = 2;
    /* POTENTIAL FLAW: 空switch语句块 */
    switch (x) {
    }
}

```
**【修复建议】**
