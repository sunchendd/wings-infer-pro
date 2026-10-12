# G.ERR.01 合理使用异常

- **规则ID**：f537de9c-77c1-43b1-9135-facb76a0e5a4
- **更新时间**：2025-06-05 04:35:02

---

**【问题级别】**

提示

**【描述】**

抛出的异常应该是Error错误或Error的子类，建议不要抛出字符串或其他对象。构造异常时应始终使用new。



自定义异常是在函数中传递附加错误信息的好方法，应在默认异常的错误类型不满足的情况下使用自定义异常。



有时候捕获了异常，什么也不做是正确的，但是应该增加注释说明原因。

**【正确示例】**

```
throw new Error('error');
try {
  return handleNumericResponse(response);
} catch (expected) {
  // 不是数字；没关系，继续
}

```
**【错误示例】**

```
throw 'error';
try {
  shouldFail();
  fail('expected an error');
} catch (expected) {}

```
**【修复建议】**

合理使用异常
