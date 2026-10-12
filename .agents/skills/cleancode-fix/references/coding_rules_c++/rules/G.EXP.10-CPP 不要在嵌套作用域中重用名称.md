# G.EXP.10-CPP 不要在嵌套作用域中重用名称

- **规则ID**：286998e9-1fc2-4ba8-9e91-97f7c15f1866
- **更新时间**：2025-03-25 19:22:21

---

**【问题级别】**

严重

**【描述】**

在嵌套的作用域中重用名称，容易给阅读者带来困扰，分不清楚实际在用哪个变量。类似地，在同一个命名空间内使用using声明的类型别名也应该唯一。

**【正确示例】**

```
如下代码示例中，使用了不同的变量名：

#define MAX_MESSAGE_LEN 100
#define CUSTOMIZED_SIZE 80

void Func(const char *str)
{
    char message[MAX_MESSAGE_LEN];
    ...
    if (str != NULL) {
        char msg[CUSTOMIZED_SIZE];
        ...
        int ret = sprintf_s(msg, sizeof(msg), "Error: %s
", str);
        ...
    }
    ...
}

int main(void)
{
    ...
    Fun("some error");

    return 0;
}

```
**【错误示例】**

```
void Fun()
{
    std::string msg;
    ...
    if (condition) {
         std::string msg;        // 不符合：外层局部变量被遮盖
         ...
    }
    ...
}
void Fun(const std::string& msg)
{
    ...
    if (condition) {
        std::string msg;         // 不符合：函数入参被遮盖
        ...
    }
}
class SomeClass {
public:
    void Fun()
    {
        std::string msg;         // 不符合：类成员变量被遮盖
        ...
    }

private:
   std::string msg;
};

```
**【修复建议】**

重命名变量
