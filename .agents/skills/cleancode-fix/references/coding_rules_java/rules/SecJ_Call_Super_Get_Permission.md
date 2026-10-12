# SecJ_Call_Super_Get_Permission

- **规则ID**：2171ad54-e1c4-481b-a0b9-74692f0d63fd
- **更新时间**：2025-06-05 04:00:03

---

**【问题级别】**

一般

**【描述】**

继承URLClassLoader类时，重载getPermissions(CodeSource)函数时没有调用super.getPermissions(...)。

**【正确示例】**

```
public class CWE358_J_Rule8_2_Call_Super_GetPermission_Good extends URLClassLoader {
	// Other code…
    
    /* POTENTIAL FLAW: 继承URLClassLoader类时，重载getPermissions(CodeSource)函数时是否调用了super.getPermissions(...)。 */
    @Override
    protected PermissionCollection getPermissions(CodeSource cs) {
        super.getPermissions(cs);
        PermissionCollection pc = new Permissions();
        // allow exit from the VM anytime
        pc.add(new RuntimePermission("exitVM"));
        return pc;
    }
    
    // Other code…
}

```
**【错误示例】**

```
public class CWE358_J_Rule8_2_Call_Super_GetPermission_Bad extends URLClassLoader {
	// Other code…
    
    /* POTENTIAL FLAW: 继承URLClassLoader类时，重载getPermissions(CodeSource)函数时是否调用了super.getPermissions(...)。 */
    @Override
    protected PermissionCollection getPermissions(CodeSource cs) {
        PermissionCollection pc = new Permissions();
        // allow exit from the VM anytime
        pc.add(new RuntimePermission("exitVM"));
        return pc;
    }
    
    // Other code…
}

```
**【修复建议】**
