# SecJ_Dead_Code_Unused_Field

- **规则ID**：cc712864-1b13-47fa-9a75-306e20b6bdf1
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

程序包含永远不会执行到的代码。

**【正确示例】**

```
public class CWE561_DeadCode_UnusedField_01 {
    private String tValue;

    private void good() {
        IO.writeLine(this.tValue);
    }
}

```
**【错误示例】**

```
public class CWE561_DeadCode_UnusedField_01 {
    /* POTENTIAL FLAW: This field is never called */
    private String value;
    private String tValue;

    private void bad() {
    }
}

```
**【修复建议】**

移除未使用的Field。
