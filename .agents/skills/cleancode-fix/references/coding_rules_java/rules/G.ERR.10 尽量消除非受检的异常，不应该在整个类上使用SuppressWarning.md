# G.ERR.10 尽量消除非受检的异常，不应该在整个类上使用SuppressWarning

- **规则ID**：4e5f9c0c-7f74-4f3d-a573-fd22b4d6eb30
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

在源代码中通过@SuppressWarning("unchecked")屏蔽告警，是个坏的实践。它丢失了类型安全和描述性的好处。



然而有些Java API，是用Object obj来存储数据对象的，当数据被取出来用时，不得不转换为用户数据对象。这时可能会有强制类型转换的告警，例如：[unchecked] unchecked method invocation。



非受检警告很重要，不要轻易忽略它们。应该始终在最小的范围内使用@SuppressWarning注解，一般是在变量声明，简短的语句或方法上。

**【正确示例】**

```
##### 场景1：@SuppressWarning注解的范围最小化
- 修复示例： 

  ```java
    public class SuppressWarnings {

        @SuppressWarnings("uncheck")
        public void doSomething(List<String> list) {
        }
    }
  ```


```
**【错误示例】**

```
##### 场景1：@SuppressWarning注解的范围最小化
- 错误示例：

  ```java
    @SuppressWarnings("uncheck")
    public class SuppressWarnings {

        public void doSomething(List<String> list) {
        }
    }
  ```


```
**【修复建议】**

如果需要使用@SuppressWarning注解来抑制告警信息，@SuppressWarning注解的应用范围应该最小化，避免直接为Class、Enum添加@SuppressWarning注解。
