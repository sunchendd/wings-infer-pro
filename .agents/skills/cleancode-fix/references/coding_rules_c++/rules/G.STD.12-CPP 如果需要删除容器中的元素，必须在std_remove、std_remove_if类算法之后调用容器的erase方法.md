# G.STD.12-CPP 如果需要删除容器中的元素，必须在std::remove、std::remove_if类算法之后调用容器的erase方法

- **规则ID**：fc2c7407-76be-46a7-ab35-d3554eb52e8e
- **更新时间**：2025-03-25 19:23:29

---

**【问题级别】**

严重

**【描述】**

在对容器调用std::remove、std::remove_if算法后，将需要保留的元素移动到被删除元素的位置上，但是没有调整容器当前的大小。对于存在特定移动方法的类型，被移动了的元素对象可能无效了。因此调用std::remove后，应调用容器对象的erase方法，该方法将容器调整为新的大小，以确保将后面已完成移动的无效元素清除。此规则通常被称之为erase-remove惯用法。



对于std::list、std::forward_list容器，使用它们的remove方法后，不需要erase。另外，C++20提供了std::erase和std::erase_if算法，其效果等价于erase-remove惯用法。

**【正确示例】**

```
nt main()
{
    std::string str1 = "Hello world Text   with some   spaces";
    str1.erase(std::remove(str1.begin(), str1.end(), ' '), str1.end());
    std::cout << str1 << std::endl;

    std::string str2 = "Hello world  Text
 with\tsome \t  white spaces

";
    auto erased = std::remove_if(str2.begin(), str2.end(),
                                 [](unsigned char x) { return std::isspace(x); });
    str2.erase(erased, str2.end());
    std::cout << str2 << std::endl;
    return 0;
}
输出：
HelloworldTextwithsomespaces
HelloworldTextwithsomewhitespaces

```
**【错误示例】**

```
int main()
{
    std::string str1 = "Hello world Text with some   spaces";
    std::remove(str1.begin(), str1.end(), ' ');
    std::cout << str1 << std::endl;

    std::string str2 = "Hello world Text 
 with\tsome \t  white spaces

";
    std::remove_if(str2.begin(), str2.end(), 
                   [](unsigned char x) { return std::isspace(x); });
    std::cout << str2 << std::endl;
    return 0;
}
输出：
HelloworldTextwithsomespaces spaces
HelloworldTextwithsomewhitespaceshite spaces

```
**【修复建议】**

不要使用erase之后的无效迭代子。如果需要删除容器中的元素，必须在std::remove、std::remove_if类算法之后调用容器的erase方法。
