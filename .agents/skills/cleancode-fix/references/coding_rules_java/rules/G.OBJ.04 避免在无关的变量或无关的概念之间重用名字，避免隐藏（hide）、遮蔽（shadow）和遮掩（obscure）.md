# G.OBJ.04 避免在无关的变量或无关的概念之间重用名字，避免隐藏（hide）、遮蔽（shadow）和遮掩（obscure）

- **规则ID**：8942f7e2-96c0-42bd-83bc-e34e0db1b191
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

严重

**【描述】**

一个变量、方法或类可以分别遮蔽（shadow）在类内部具有相同名字的变量、方法或类。如果一个实体被遮蔽了，那么就无法用简单名引用到它。



对于以下场景工具不会告警：



- 构造器参数变量

- setter方法参数变量

**【正确示例】**

```
##### 场景1：
- 修复示例： 

  ```java
     public class HiddenField {
        Object obj;
    
        public void doSomething(Object prama) {
            ...
        }
        ...
    }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例： 

  ```java
    public class HiddenField {
        Object obj;
    
        public void doSomething(Object obj) {
            ...
        }
        ...
    }
  ```


```
**【修复建议】**

对于方法中的临时变量，避免与类的属性重名。
