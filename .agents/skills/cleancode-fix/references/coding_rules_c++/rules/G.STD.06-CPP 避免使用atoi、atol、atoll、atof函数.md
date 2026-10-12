# G.STD.06-CPP 避免使用atoi、atol、atoll、atof函数

- **规则ID**：ad1b04c7-a48d-4610-bf1a-433b947c42ad
- **更新时间**：2025-03-25 19:23:26

---

**【问题级别】**

一般

**【描述】**

C标准库中的atoi, atol, atoll, atof函数，在字符串转换的结果无法表示成相应的数值时，会导致程序产生未定义行为，并且未提供足够的出错信息。应使用C++的stoi, stol, stoll，stof, stod, stold等函数替代它们，或者使用C标准库中的strtol, strtoll, strtof, strtod, strtold等函数代替它们。



c++11开始提供了stoi, stol, stoll，stof, stod, stold等函数，使用这些函数时需要处理无法正确转换的异常。在禁用异常的场景中，可以使用C标准库中的strtol, strtoll, strtof, strtod, strtold等函数，并处理未成功转换的错误。

**【正确示例】**

```
td::string str = GetInputStr();

try {
    int num = std::stoi(str.c_str());
    std::cout << num << std::endl;
} catch (const std::invalid_argument& e) {
    ... // 错误处理
} catch (const std::out_of_range& e) {
    ... // 错误处理
}

```
**【错误示例】**

```
std::string str = GetInputStr();
int num = std::atoi(str.c_str());
…

```
**【修复建议】**

避免使用atoi以及scanf类函数将字符串转换为整数或者浮点数。可选择strto*类型函数来解析字符串中的整数或浮点数，因为该类函数提供更强大的错误处理能力。
