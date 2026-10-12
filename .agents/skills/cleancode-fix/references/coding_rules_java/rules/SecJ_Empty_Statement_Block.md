# SecJ_Empty_Statement_Block

- **规则ID**：202b2e4e-723e-4055-b105-cded88e04f77
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

不正确的风格

**【正确示例】**

```
public class CWE391_J_Rule_EmptyStatementBlock_Good {
    private int _bar;

    public void setBar(int bar) {
        {
            _bar = bar;
        }
        {
            doSomeThing();
        }
    }
}

```
**【错误示例】**

```
public class CWE391_J_Rule_EmptyStatementBlock_Bad {
    private int _bar;

    public void setBar(int bar) {
        {
            _bar = bar;
        }
        /* POTENTIAL FLAW: 空语句块 */
        {
        }
    }
}

```
**【修复建议】**
