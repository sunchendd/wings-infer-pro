# G.FMT.06-CPP 换行时将操作符留在行末，新行缩进一层或进行同类对齐

- **规则ID**：c1aec973-1f90-45fa-8923-e51c27b1dfe8
- **更新时间**：2025-03-25 19:21:51

---

**【问题级别】**

一般

**【描述】**

当语句过长，或者可读性不佳时，需要在合适的地方换行。

换行时将操作符、连接符放在行末，表示“未结束，后续还有”。新行缩进一层，或者保持同类对齐。



调用函数的参数列表换行时，左圆括号总是跟函数名，右圆括号总是跟最后一个参数，并进行合理的参数对齐。



一般选择在较低优先级操作符或连接符后换行，或者根据表达式层次换行。

**【正确示例】**

```
长表达式举例：

// 假设下面第一行已经不满足行宽要求
if (currentValue > MIN &&  // 符合：换行后，布尔操作符放在行末
    currentValue < MAX) {  // 符合: 与(&&)操作符的两个操作数同类对齐
    DoSomething();
    ...
}

flashPara.flashEndAddr = flashPara.flashBaseAddr +  // 符合: 加号留在行末
                         flashPara.flashSize;       // 符合: 加法两个操作数对齐
函数参数列表举例：

// 符合：函数参数放在一行
ReturnType result = FunctionName(paramName1, paramName2);

ReturnType result = FunctionName(paramName1,
                                 paramName2,
                                 paramName3); // 符合：保持与上方参数对齐

ReturnType result = FunctionName(paramName1, paramName2,
    paramName3, paramName4, paramName5);     // 符合：参数换行，4 空格缩进

ReturnType result = VeryVeryVeryLongFunctionName( // 行宽不满足第1个参数，直接换行
    paramName1, paramName2, paramName3);          // 换行后，4 空格缩进
如果函数的参数存在内在关联性，按照可理解性优先于格式排版要求，对参数进行合理分组换行。

// 符合：每行的参数代表一组相关性较强的数据结构，放在一行便于理解
int result = DealWithStructLikeParams(left.x, left.y,    // 表示一组相关参数
                                      right.x, right.y); // 表示另外一组相关参数
初始化语句举例：

// 符合: 满足行宽要求时不换行
int arr[4] = { 1, 2, 3, 4 };
// 符合: 行宽较长时，换行让可读性更好
const int rank[] = {
    16, 16, 16, 16, 32, 32, 32, 32,
    64, 64, 64, 64, 32, 32, 32, 32
};
对于复杂结构数据的初始化，尽量清晰、紧凑。
参考如下格式：

int a[][4] = {
    { 1, 2, 3, 4 }, { 2, 2, 3, 4 }, // 符合
    { 3, 2, 3, 4 }, { 4, 2, 3, 4 }
};

int b[][8] = {
    { 1, 2, 3, 4, 5, 6, 7, 8 },     // 符合
    { 2, 2, 3, 4, 5, 6, 7, 8 }
};
int c[][8] = {
    {
        1, 2, 3, 4, 5, 6, 7, 8      // 符合
    }, {
        2, 2, 3, 4, 5, 6, 7, 8
    }
};
对于初始化语句中的大括号，遵循：

左大括号放行末时，对应的右大括号需另起一行
左大括号被内容跟随时，对应的右大括号也应跟随内容

```
**【错误示例】**

```
ReturnType result = FunctionName(paramName1,
 paramName2); // 不符合，未按要求对齐


flashPara.flashEndAddr = flashPara.flashBaseAddr 
      +  flashPara.flashSize;       // 不符合，操作符应该在上一行末

```
**【修复建议】**

按要求进行对齐
