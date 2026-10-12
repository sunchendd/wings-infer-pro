# G.NAM.02-CPP C++文件名和类名保持一致

- **规则ID**：d539a0bc-4da6-4252-a7bc-a6862765e63f
- **更新时间**：2025-03-25 19:21:42

---

**【问题级别】**

一般

**【描述】**

C++的头文件和源文件名应该和类名保持一致，可以使用大驼峰或者小写下划线风格。项目组可以选择一种风格约定执行，并保持风格统一。



例如，有一个类叫DatabaseConnection，那么对应的文件名如下：



DatabaseConnection.h

DatabaseConnection.cpp

或者使用如下文件名：



database_connection.h

database_connection.cpp

结构体，命名空间，枚举等定义的文件名类似。

**【正确示例】**

```


```
**【错误示例】**

```


```
**【修复建议】**

修改文件名或类名
