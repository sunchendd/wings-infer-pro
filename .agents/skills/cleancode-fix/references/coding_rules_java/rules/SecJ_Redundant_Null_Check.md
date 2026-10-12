# SecJ_Redundant_Null_Check

- **规则ID**：7ac97e54-4424-4361-9e49-51e9deab1132
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

多余的空指针判断，已知对象不为空或者已使用对象，后面再对对象做判空操作则会触发此规则。

**【正确示例】**

```
public void bad(String myString) throws Throwable {
        {
            if (myString != null) {
                myString = "my, how I've changed";
            }
            IO.writeLine(myString.length());
        }
    }

```
**【错误示例】**

```
public void bad(String myString) throws Throwable {
        {
            /* POTENTIAL FLAW: Check for null after dereferencing the object. This null check is unnecessary. */
            IO.writeLine(myString.length());

            if (myString != null) {
                myString = "my, how I've changed";
            }
        }
    }

```
**【修复建议】**

已知对象不为null则可不用检查空指针；不能确定对象是否为null，则在使用对象前进行空指针检查。
