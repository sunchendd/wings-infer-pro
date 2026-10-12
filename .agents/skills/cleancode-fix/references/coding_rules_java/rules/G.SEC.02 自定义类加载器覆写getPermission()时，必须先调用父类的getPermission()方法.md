# G.SEC.02 自定义类加载器覆写getPermission()时，必须先调用父类的getPermission()方法

- **规则ID**：468d6fd6-14a8-4683-afdf-ca995756e068
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

自定义类加载器，如果需要重写 getPermissions() 方法时，在给其它代码设置权限之前，必须要先调 用父类的 getPermissions() 方法来应用默认的安全策略。自定义类加载器如果忽略调用父类的 getPermissions() 方法，该类加载器可以加载提升权限的不可信类

**【正确示例】**

```
getPermissions()方法调用父类的getPermissions()来使用全局的默认安全策略。
public class MyClassLoader extends URLClassLoader {
    public MyClassLoader(URL[] urls) {
        super(urls);
    }
    @Override
    protected PermissionCollection getPermissions(CodeSource cs) {
        PermissionCollection pc = super.getPermissions(cs);
        // 允许任何时间退出VM
        pc.add(new RuntimePermission("exitVM"));
        return pc;
    }
    // 其他代码
}

```
**【错误示例】**

```
示例代码是一个继承自URLClassLoader类的自定义类加载器的一部分。它重写了 getPermissions() 方法，但没有调用父类的 getPermissions() 方法。因此，被该加载器加载的类具有的权限会独立于系统全局安全策略规定的权限。
public class MyClassLoader extends URLClassLoader {
    public MyClassLoader(URL[] urls) {
        super(urls);
    }
    @Override
    protected PermissionCollection getPermissions(CodeSource cs) {
        PermissionCollection pc = new Permissions();
        // 允许任何时间退出VM
        pc.add(new RuntimePermission("exitVM"));
        return pc;
    }
    // 其他代码
}

```
**【修复建议】**

继承URLClassLoader类时，重载getPermissions(CodeSource)方法时需要调用super.getPermissions()
