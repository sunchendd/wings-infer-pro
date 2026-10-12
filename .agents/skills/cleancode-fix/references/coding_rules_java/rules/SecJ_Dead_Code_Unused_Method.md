# SecJ_Dead_Code_Unused_Method

- **规则ID**：1ded5c78-e711-4012-8b63-0a8ede211ff7
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

程序包含永远不会执行到的代码。

**【正确示例】**

```
public class CWE561_DeadCodeUnusedMethod_Good_01 {
    private void bad() {
    }

    public void good () {
        bad();
    }
}

```
**【错误示例】**

```
public class CWE561_DeadCodeUnusedMethod_Bad_01 {
    /* POTENTIAL FLAW: This method is never called */
    private void bad() {
    }
}

```
**【修复建议】**

删除程序中永远不会执行到的方法或者确定其能被调用。
