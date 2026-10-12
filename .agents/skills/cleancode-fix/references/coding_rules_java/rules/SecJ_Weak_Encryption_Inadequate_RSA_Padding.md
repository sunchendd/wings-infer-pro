# SecJ_Weak_Encryption_Inadequate_RSA_Padding

- **规则ID**：483e2896-064b-4ace-aa30-bbb5bcc20034
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

实际中，使用 RSA 公钥的加密通常与某种填充模式结合使用。该填充模式的目的在于防止一些针对 RSA 的攻击，这些攻击仅在执行不带填充模式的加密时才起作用。

**【正确示例】**

```
public void testGood() throws Exception {
    Cipher.getInstance("RSA/ECB/OAEPPadding");
}

```
**【错误示例】**

```
public void testBad() throws Exception {
    /* POTENTIAL FLAW: RSA 算法在没有 OAEP 填充模式下使用，因此加密机制比较脆弱。 */
    Cipher.getInstance("RSA");
    /* POTENTIAL FLAW: RSA 算法在没有 OAEP 填充模式下使用，因此加密机制比较脆弱。 */
    Cipher.getInstance("RSA/ECB/NoPadding");
}

```
**【修复建议】**

为安全使用RSA，在执行加密时推荐使用OAEP（最优非对称加密填充模式）。
