# G.VAR.02 不要在子作用域中重用变量名

- **规则ID**：e4ff6516-d701-4515-8845-38f0013c246d
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

严重

**【描述】**

一个作用域包含另一个作用域时，不要在这两个作用域中使用相同的变量名。

**【正确示例】**

```
##### 场景1：两个作用域中使用相同的变量名
- 修复示例：

  ```c
  #define MAX_MESSAGE_LEN 100
  #define CUSTOMIZED_SIZE 80
  void Func(const char *str)
  {
      char message[MAX_MESSAGE_LEN];
      ...
      if (str != NULL) {
          char customMsg[CUSTOMIZED_SIZE]; // 符合
          ...
          int ret = sprintf_s(customMsg, sizeof(customMsg), "Error: %s
", str);
          ...
      }
      ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：两个作用域中使用相同的变量名
- 错误示例：

  ```c
  #define MAX_MESSAGE_LEN 100
  #define CUSTOMIZED_SIZE 80
  void Func(const char *str)
  {
      char message[MAX_MESSAGE_LEN];
      ...
      if (str != NULL) {
          char message[CUSTOMIZED_SIZE];  // 不符合：使用了与外层相同的变量名
          ...
          // MAX_MESSAGE_LEN 使用错误
          int ret = sprintf_s(message, MAX_MESSAGE_LEN, "Error: %s
", str);
          ...
      }
      ...
  }
  ```


```
**【修复建议】**

修改变量名，保证两个作用域中变量不重名。
