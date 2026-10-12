# G.OBJ.02 不要在父类的构造方法中调用可能被子类覆写的方法

- **规则ID**：72e83bb4-7ca6-459f-8f31-48221e80f3c7
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

当在父类的构造方法中调用可能被子类覆写的方法时，构造方法的表现是不可预知的，很可能会导致异常。而问题出现后，往往难以快速定位。

这是由于在Java中，当子类初始化时，会调用父类的构造方法，当父类构造方法调用了被子类覆写的方法，往往会由于子类的初始化未完成而导致异常。

**【正确示例】**

```
##### 场景1：
- 修复示例1：构造方法中调用private方法

```java
public class SeniorClass {
    public SeniorClass() {
        doSomething() ;  // 【GOOD】构造方法中调用private方法
    }
    private String doSomething() {
        ...
        return "IAmSeniorClass";
    }
}
```
- 修复示例2：构造方法中调用final方法
```java
public class SeniorClass {
    public SeniorClass() {
        doSomething() ; // 【GOOD】构造方法中调用final方法
    }
    public final String doSomething() {
        ...
        return "IAmSeniorClass";
    }
}
```
- 修复示例3：final类
```java
// 【GOOD】final类
public final class SeniorClass {
    public SeniorClass() {
        doSomething() ;  
    }
    public String doSomething() {
        ...
        return "IAmSeniorClass";
    }
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

```java
public class SeniorClass {
    public SeniorClass() {
        toString(); // 【不符合】如果toString()被覆写了，可能会导致异常
    }
    @Override
    public String toString() {
        return "IAmSeniorClass";
    }
}
public class JuniorClass extends SeniorClass {
    private String name;
    public JuniorClass() {
        super(); // 【不符合】调用父类的构造方法，导致NullPointerException异常
        name = "JuniorClass";
    }
    @Override
    public String toString() {
        return name.toUpperCase();
    }
}
```


```
**【修复建议】**

1. 将需要调用的方法修改为private修饰（构造方法中调用private方法）

2. 将需要调用的方法修改为final修饰（构造方法中调用final方法）

3. 将类修改为final类
