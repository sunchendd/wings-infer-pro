# G.RES.08-CPP 使用RAII技术管理资源的生命周期

- **规则ID**：c77d2eda-23d8-47ba-ae4a-43deada7a39a
- **更新时间**：2025-03-25 19:22:43

---

**【问题级别】**

一般

**【描述】**

RAII代表 resource acquisition is initialization。它可以用于避免手工资源管理的复杂性。



资源的获取和释放是成对操作（例如new/delete，fopen/fclose，lock/unlock 等），恰好能对应C++语言对称的构造函数和析构函数。利用C++对象的生命周期来管理资源的生命周期，是一种常见的策略。

**【正确示例】**

```
void ReadFile(const char* fileName)
{
    std::ifstream file(fileName);  // file 会在函数结束的时候自动关闭
    if (file.fail()) {
        std::cout << "failed to open " << fileName << std::endl;
        return;
    }  
    DoSomething(file);
}

```
**【错误示例】**

```
#include <cstdio>
#include <cstdlib>

void ReadFile(const char* fileName)
{
    FILE* fp = std::fopen(fileName, "r");
    if (fp == nullptr) {
        std::cout << "failed to open " << fileName << std::endl;
        return;
    }
    DoSomething(fp); // 如果抛异常，则文件没有被正确关闭
    close(fp);
}

```
**【修复建议】**

使用RAII管理资源
