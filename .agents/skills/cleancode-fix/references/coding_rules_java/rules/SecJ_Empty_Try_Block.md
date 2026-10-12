# SecJ_Empty_Try_Block

- **规则ID**：5c07a54f-9e97-46f5-abc5-23d88ca81605
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

程序包含永远不会执行到的代码。

**【正确示例】**

```
public class CWE391_J_Rule_EmptyTryBlock_Good {
    public void test01Good() {
        try {
            doSomeThing();
        } catch (Exception e) {
            LOG.info(e.getMessage());
        }
    }
}

```
**【错误示例】**

```
public class CWE391_J_Rule_EmptyTryBlock_Bad {
    public void test01Bad() {
        /* POTENTIAL FLAW: 空try块 */
        try {
            // not good
        } catch (Exception e) {
            LOG.info(e.getMessage());
        }
    }
}

```
**【修复建议】**
