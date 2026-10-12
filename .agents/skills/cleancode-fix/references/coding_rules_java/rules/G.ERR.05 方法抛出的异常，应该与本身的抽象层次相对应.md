# G.ERR.05 方法抛出的异常，应该与本身的抽象层次相对应

- **规则ID**：06b957cc-46e4-442c-9abe-c002dfbb6933
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

方法抛出异常时，应该避免直接抛出RuntimeException，更不应该直接抛出Exception或Throwable，因为这些父类异常无法与异常发生的场景相关联，直接抛出父类异常会降低代码可读性。方法抛出的异常应该与方法本身的抽象层次相对应，这些异常可以是JDK中定义的标准异常，也可以是业务层自定义的异常。另外，抛出的异常中应该包含理解该异常产生原因的所有信息。

**【正确示例】**

```
##### 场景1：
- 修复示例： 

  ```java
    public class Employee {
        ...
        public String getSomeInfo() throws MyBizException{
            ...
            throw new MyBizException("xxx");
        }
        ...
    }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：直接抛出RuntimeException

  ```java
    public class Employee {
        ...
        public String getSomeInfo() {
            ...
            throw new RuntimeException("xxx");
        }
        ...
    }
  ```


```
**【修复建议】**

方法抛出的异常应该是含有明确异常产生原因的具体异常类型（非基类异常）。
