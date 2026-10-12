# G.OBJ.10 接口定义中去掉多余的修饰词

- **规则ID**：75ab8c86-f9e5-4aea-9459-6ced37b27c2d
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

在接口定义中，属性缺省具有public static final修饰词，非默认方法缺省具有public abstract修饰词。代码中不需要再次提供这些修饰词。

**【正确示例】**

```
##### 场景1：接口中的属性缺省修饰符需省略
- 修复示例： 接口属性声明中不使用冗余修饰符

  ```java
    public interface ParameterSetNameInterface {
        int STATIC_VAR = 100;
    }
  ```


```
**【错误示例】**

```
##### 场景1：接口中的属性缺省修饰符需省略
- 错误示例：接口的属性声明使用了冗余的`public static final`修饰符

  ```java
    public interface ParameterSetNameInterface {
        public static final int STATIC_VAR = 100;
    }
  ```


```
**【修复建议】**

删除接口中的属性与非默认方法的缺省修饰符。



通过类名调用
