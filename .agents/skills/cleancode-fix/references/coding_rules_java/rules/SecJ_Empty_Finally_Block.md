# SecJ_Empty_Finally_Block

- **规则ID**：b0fa5112-8a59-4688-8917-760619bfe5b7
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

不正确的风格

**【正确示例】**

```
public void test01Good() {
    try {
        int x = 2;
    } finally {
        doSomeThing();
    }
}

```
**【错误示例】**

```
public void test01Bad() {
    try {
        int x = 2;
    }/* POTENTIAL FLAW: 空finally块 */ finally {
        // empty!
    }
}

```
**【修复建议】**
