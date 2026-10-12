# G.FMT.07 应该避免空块，必须使用空块时，应采用统一的大括号换行风格

- **规则ID**：304dab4e-7e99-48b7-920b-f68248770fca
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

程序中应避免空块，但对于工具自动生成的、用于被覆盖的场景（例如UI监听器），可能需要定义空的方法体；忽略异常时也可能使用空的catch块。

**【正确示例】**

```
##### 场景1：代码中存在空块
- 修复示例：

  ```java
  class EmptyBlockDemo {
      ...
      public void doSomething() {
          int data = 1;
          ...        
      }
  
  }
  ```


```
**【错误示例】**

```
##### 场景1：代码中存在空块
- 错误示例：

  ```java
  class EmptyBlockDemo {
      static {
  
      }
      ...
      public void doSomething() {
          int data = 1;
          ...
          for (String str : list) {
          }
          ...
      }
  
  }
  ```


```
**【修复建议】**

建议将代码中的无效空块删除。
