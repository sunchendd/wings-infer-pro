# SecJ_Constructor_Invokes_Overridable_Function

- **规则ID**：b6d155fe-41be-4448-b20c-92bf1645ed76
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

当在父类的构造方法中调用可能被子类覆写的方法时，构造方法的表现是不可预知的，很可能会导致异常。而问题出现后，往往难以快速定位。 这是由于在Java中，当子类初始化时，会调用父类的构造方法，当父类构造方法调用了被子类覆写的方法，往往会由于子类的初始化未完成而导致异常。

**【正确示例】**

```
package CodeCorrectness.ConstructorInvokesOverridableFunction;

import org.springframework.util.StringUtils;


public class CodeCorrectness_ConstructorInvokesOverridableFunction_Internal_PublicMethod_01 {

    private String username;
    private boolean valid;

    public CodeCorrectness_ConstructorInvokesOverridableFunction_Internal_PublicMethod_01(String username, String password){
        this.username = username;
    }

    public boolean validateUser(String username, String password) {
        if(!StringUtils.isEmpty(username) && !StringUtils.isEmpty(password)){
            return true;
        }
        return false;
    }
}

```
**【错误示例】**

```
package CodeCorrectness.ConstructorInvokesOverridableFunction;

import org.springframework.util.StringUtils;

public class CodeCorrectness_ConstructorInvokesOverridableFunction_Internal_PublicMethod_01 {

    private String username;
    private boolean valid;

    public CodeCorrectness_ConstructorInvokesOverridableFunction_Internal_PublicMethod_01(String username, String password){
        this.username = username;
        /* POTENTIAL FLAW:  类的构造函数调用了可被覆盖的函数。 */
        this.valid = validateUser(username,password);
    }

    public boolean validateUser(String username, String password) {
        if(!StringUtils.isEmpty(username) && !StringUtils.isEmpty(password)){
            return true;
        }
        return false;
    }
}

```
**【修复建议】**

不要在父类的构造方法中调用可能被子类覆写的方法
