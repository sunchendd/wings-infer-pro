# G.FMT.19 类和成员修饰符（如果存在）按Java语言规范建议的顺序显示

- **规则ID**：f1290f68-16f1-4636-8c02-09274fae601a
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

类和成员修饰符（如果存在）按推荐的顺序显示（如果存在）：



```java

public protected private abstract default static final transient volatile synchronized native strictfp

```

**【正确示例】**

```
##### 场景1：类和成员修饰符与推荐顺序不一致
- 修复示例1：

  ```java
  public class ModifierOrder {
      private static final int II = 0;
      
      private synchronized void doSomething(String str) throws IOException {
          int num = 0;
          ...
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：类和成员修饰符与推荐顺序不一致
- 错误示例：

  ```java
  public class ModifierOrder {
      private final static int II = 0;
      
      synchronized private void doSomething(String str) throws IOException {
          int num = 0;
          ...
      }
  }
  ```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
