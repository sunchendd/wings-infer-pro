# G.DCL.05 禁止将mutable对象声明为public static final

- **规则ID**：fb754379-fe55-4348-b8ea-3b8b6d5f7a40
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

使用public static final的意图是定义一个常量。如果用其修饰一个mutable（可变）对象，极易产生不当使用，造成功能异常。

**【正确示例】**

```
##### 场景1：两个List集合都是mutable，不应该定义为常量
- 修复示例1：

  ```java
  public static final List<String> EMPTY_RESULT_LIST = Collections.unmodifiableList(new ArrayList<>());
  public static final List<String> EMPTY_RESULT_LIST = Collections.emptyList();
  ```
- 修复示例2：

  ```java
  private static final List<String> infoList= new ArrayList<>();
  ```

```
**【错误示例】**

```
##### 场景1：两个List集合都是mutable，不应该定义为常量
- 错误示例：

  ```java
  public static final List<String> EMPTY_RESULT_LIST = new ArrayList<>();
  public static final List<String> RESULT_LIST = Arrays.asList("result1", "result2");
  ```


```
**【修复建议】**

对于`public static final`修饰的mutable对象，应该使用小驼峰命名，或者是将mutable对象修改为immutable对象，并使用大写字母命名。
