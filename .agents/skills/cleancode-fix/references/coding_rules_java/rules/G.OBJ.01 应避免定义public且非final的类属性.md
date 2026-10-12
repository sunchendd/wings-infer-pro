# G.OBJ.01 应避免定义public且非final的类属性

- **规则ID**：2fa10489-7035-45a7-be6c-92ce56ada581
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

提示

**【描述】**

应避免定义public且非final的类属性。将类的属性设置为私有（private）的理由是：不希望类的外部代码依赖这个属性，依赖类内部的实现细节。这样，当内部实现需要变更时，影响面就比较小，变更的成本就比较低。

**【正确示例】**

```
##### 场景1：
- 修复示例：将public类型的成员变量改为private类型

```java
public class UserInfo {
    private String userName;
    private String addr;
    private int age;
	
    ...
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：类含有public类型的成员变量

```java
public class UserInfo {
    public String userName;
    public String addr;
    public int age;

    ...
}
```


```
**【修复建议】**

将public类型的属性更改为private或设置为final。
