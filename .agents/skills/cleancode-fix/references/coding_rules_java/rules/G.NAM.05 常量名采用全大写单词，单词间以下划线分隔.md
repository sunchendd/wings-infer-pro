# G.NAM.05 常量名采用全大写单词，单词间以下划线分隔

- **规则ID**：bca6655a-687f-432d-aa62-f3952cadd09a
- **更新时间**：2026-04-07 04:00:00

---

**【问题级别】**

提示

**【描述】**

java规范中的常量是指不可被修改静态的field和枚举常量。“不可被修改”需要同时满足以下两个条件：



- field的值/对象不可被修改为其他的值/对象；

- field为对象类型时，对象在初始化完成后其属性不能被修改。



常量定义的一般格式为：`[访问修饰符] static final 类型 常量名 = 常量值;`。



常量命名应该由**全大写单词与下划线**组成，单词间用下划线分隔，如CONSTANT_CASE。常量命名要尽量表达完整的语义。



不要使用魔鬼数字（难以理解的数字或字符串)，用有意义的常量代替。SQL或日志的字符串，不应视为魔鬼数字，不需定义为字符串常量；

**【正确示例】**

```
##### 场景1
- 修复示例
  ```java
  static final int MAX_USER_NUM = 200; // 【GOOD】MAXUSERNUM-->MAX_USER_NUM  ，并用final修饰。

  static final String APPLICATION_NAME = "Launcher"; // 【GOOD】sL-->APPLICATION_NAME ，并用final修饰。

  static final int MAX_FILE_NUM = 5; // 【GOOD】
  ```


```
**【错误示例】**

```
##### 场景1
- 错误示例
  ```java
  static final int MAXUSERNUM = 200; // 【不符合】单词间应该以下划线分隔

  static final String ApplicationName = "Launcher"; // 【不符合】常量名应该采用全大写单词，单词间以下划线分隔

  static final int NUM_FIVE = 5; // 【不符合】

  static final int NUM_5 = 5; // 【不符合】
  ```


```
**【修复建议】**

对于常量，应该采用全大写单词与下划线进行命名。



对于魔鬼数字，可采用如下方法进行优化：

- 如果有现成的API，不要定义数字，比如判断集合内元素是否为空时，不应该使用size() == 0，应使用isEmpty()方法；比如时间的比较判断，用java.time中的API；

- 有命名模式的可以用枚举类型。
