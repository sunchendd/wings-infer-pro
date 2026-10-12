# G.SEC.01 进行安全检查的方法必须声明为private或final

- **规则ID**：91b43e61-781f-4921-b849-46b9b9dfda49
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

如果一个方法被子类覆盖，则该子类可绕过其父类中的安全检查。

**【正确示例】**

```
private void good() {
        SecurityManager sm = System.getSecurityManager();
        if (sm != null) {
            sm.checkPermission(new SecurityPermission("SomeAction"));
        }
        // ...
    }

```
**【错误示例】**

```
/* POTENTIAL FLAW: 用于执行安全检查的非最终方法可能会被绕过安全检查的多种方式覆盖 */
    public void bad() {
        SecurityManager sm = System.getSecurityManager();
        if (sm != null) {
            sm.checkPermission(new SecurityPermission("SomeAction"));
        }
        // ...
    }

```
**【修复建议】**

请确保所有执行安全操作的方法都已在 final 类中声明，或者这些方法本身已声明为最终。
