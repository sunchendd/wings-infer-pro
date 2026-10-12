# G.DCL.04 避免枚举常量序号的产生依赖于ordinal()方法

- **规则ID**：2061f204-bded-4d8c-8060-96310fee06f7
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

Java枚举类型通过`ordinal()`方法返回枚举常量的排列序号。默认情况下，序号是根据声明顺序从0开始累加，但某些情况下会希望指定某些枚举常量为某个固定值以代表特殊意义（例如，键盘某个按键的具体编码），返回该固定值的方法不应基于`ordinal()`方法来实现。

**【正确示例】**

```
##### 场景1：新增枚举常量时可能会导致原有枚举常量的值发生变化
- 修复示例1：

  ```java
  enum Keyboard {
      MOUSE_KEY_LEFT(1),
      MOUSE_KEY_RIGHT(2),
      MOUSE_KEY_CANCEL(4),
      MOUSE_KEY_MIDDLE(8);

      private final int mouseKeyValue;

      Keyboard(int value) {
          this.mouseKeyValue = value;
      }

      public int getMouseKeyValue() {
          return mouseKeyValue;
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：新增枚举常量时可能会导致原有枚举常量的值发生变化
- 错误示例：

  ```java
  enum Keyboard {
      MOUSE_KEY_LEFT,
      MOUSE_KEY_RIGHT,
      MOUSE_KEY_CANCEL,
      MOUSE_KEY_MIDDLE;

      public int getMouseKeyValue() {
          return ordinal() + 1;
      }
  }
  ```


```
**【修复建议】**

为枚举常量赋固定的值，消除对ordinal()方法的依赖。
