# SecJ_Empty_Synchronized_Block

- **规则ID**：7d1291a6-5fee-41c1-a2b4-898a29580747
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

不正确的风格

**【正确示例】**

```
public void test01Good() {
    synchronized (this) {
        doSomeThing();
    }
}

```
**【错误示例】**

```
public void test01Bad() {
    /* POTENTIAL FLAW: 空synchronized语句块 */
    synchronized (this) {
        // empty!
    }
}

```
**【修复建议】**
