# G.CNS.02-CPP 不要使用难以理解的字面常量

- **规则ID**：392a23cc-dd6e-4bed-83d1-f27210c1e5ef
- **更新时间**：2025-03-25 19:22:13

---

**【问题级别】**

严重

**【描述】**

难以理解的字面量是指通过代码的上下文难以明确业务含义的字面量，包括整型字面量、浮点数字面量、布尔字面量和字符串字面量等。



有时候字面量在上下文中是能够理解其含义的，有时候则不能：

例如：value = 1000; 不能明确1000代表什么类型；但 millisecond = second * 1000; 可以很容易理解为1秒是1000毫秒。

又如：数字 0 有时候也是难以理解的，比如 status = 0;，无法明确 0 是什么状态。



解决途径：



对于单点使用的难以理解的字面量，按需增加注释说明

对于多处使用的难以理解的字面量，应该定义为 constexpr 或 const 常量，并通过符号命名自注释

**【正确示例】**

```
constexpr int SERV_TYPE_SET = 1;
constexpr int SERV_TYPE_QUERY = 4;
constexpr int ADULT_AGE = 18;
int currentType = psInParam->GetValue("servType");

if (currentType == SERV_TYPE_SET) {
    ...
} else if (currentType == SERV_TYPE_QUERY) {
    ...
} else {
    ...
}

if (age >= ADULT_AGE) {
    ...
} else {
    ...
}
const std::string VERSION{"V100R011C10"};
...
std::string srcDataVer;
...
bool cond = (srcDataVer.find(VERSION) == 0);

```
**【错误示例】**

```
int currentType = psInParam->GetValue("servType");

// 下面使用的整数字面量，不容易理解其具体含义  
if (currentType == 1) {
    ...
} else if (currentType == 4) {
    ...
} else {
    ...
}

if (age >= 18) {
    ...
} else {
    ...
}
char srcDataVer[VERSION_MAX_LEN] = {0};
...
bool cond = (strncmp(srcDataVer, "V100R011C10", strlen("V100R01C10")) == 0);

```
**【修复建议】**

对于单点使用的难以理解的常量，按需增加注释说明。对于

多处使用的难以理解的常量，应该定义宏或 const 变量，并通过符号命名自注释 。
