# G.NAM.03-CPP 使用统一的命名风格

- **规则ID**：b6baea9b-dbdf-44ea-beeb-e3a3c006fffc
- **更新时间**：2025-03-25 19:21:43

---

**【问题级别】**

一般

**【描述】**

标识符命名风格原则



具体的风格由项目组自行选择，并保持风格统一

推荐使用驼峰命名风格，不推荐使用匈牙利命名风格

对于更亲和标准库的代码，可以使用标准库命名风格

基于开源或外部代码进行开发或维护时，可以保持原有命名风格

常见的命名风格



驼峰命名风格(CamelCase)

大小写字母混用，单词连在一起，不同单词间通过单词首字母大写来分开。

根据连接后的首字母是否大写，分为两种风格：大驼峰(UpperCamelCase)和小驼峰(lowerCamelCase)。



内核命名风格(unix_like)

又称蛇形风格(snake_case)，标准库使用该风格。单词全小写，用下划线分割。

如：’test_result’。



匈牙利命名风格

在“大驼峰”的基础上，加上类型或用途前缀。

如：’uiSavedCount’, ‘bTested’。

**【正确示例】**

```
##### 场景1：全局变量命名没有`g_`前缀
- 修复示例：

```cpp
int g_variable;                 // 符合：全局变量，带g_前缀的小驼峰

SomeClass g_someObject{};       // 符合：全局对象，带g_前缀的小驼峰

static int g_blockCount = 0;    // 符合：文件作用域中的全局变量，带g_前缀的小驼峰

namespace Utils {
int g_fileCount = 0;            // 符合：命名空间中的全局变量，带g_前缀的小驼峰
}

```

```
**【错误示例】**

```
##### 场景1：全局变量命名没有`g_`前缀
- 错误示例：

```cpp
int Global_variable = 7;    // 不符合

SomeClass G_someObject{};   // 不符合

static int blockCount = 0;  // 不符合

namespace Utils {
int file_Count = 0;         // 不符合
}
```

```
**【修复建议】**

修改变量名称
