# G.ERR.08-CPP 如果catch子句中不做任何操作，应添加注释说明原因

- **规则ID**：b7819469-0412-459e-9906-8b29be75489b
- **更新时间**：2025-03-25 19:22:43

---

**【问题级别】**

一般

**【描述】**

有的时候，程序员会因为程序抛出了异常，而想当然地使用try捕获异常，在catch里什么也不做，以使程序不再因异常而终止。但是，捕获到异常而不处理，相当于掩盖了问题。空白的catch块通常是这种掩盖问题的做法的表现。



然而，有时候，某些异常的正确处理方法就是什么也不做，例如：



对肮脏的数据进行统计时，忽略坏的数据，剩余的好数据仍然具有统计学意义

对于IO操作，如果因为读到输入的结尾而抛出异常，就应该停止读取，继续下一步工作

为了区别有意的“什么也不做”和因为疏忽而“掩盖异常”，应在空的catch块中添加注释，说明为何什么也不做。

**【正确示例】**

```
std::vector<double> results;
for (auto& data : dataSet) {
    try {
        double result = Process(data);
        results.push_back(result);
    } catch (const BadDataException& e) {
        // 忽略错误的数据。虽然数据集没有被清理，但已有足够的好数据来计算最终结果
    }
}

```
**【错误示例】**

```
std::vector<double> results;
for (auto& data : dataSet) {
    try {
        double result = Process(data);
        results.push_back(result);
    } catch (const BadDataException& e) {
    }
}

```
**【修复建议】**

添加异常处理或者注释说明
