# SecJ_Weak_Cryptographic_Hash_Iteration_Count

- **规则ID**：0daec611-37fe-4279-988e-35fc5c15dd75
- **更新时间**：2025-06-05 04:00:04

---

**【问题级别】**

一般

**【描述】**

迭代次数默认推荐10,000,000次，对于性能有特殊要求（比如嵌入式系统）的产品最低可迭代1000次。

**【正确示例】**

```
public static byte[] createHash(char[] password) throws NoSuchAlgorithmException, InvalidKeySpecException {
    SecureRandom random = SecureRandom.getInstance("SHA1PRNG");
    byte[] salt = new byte[8];
    random.nextBytes(salt);
    PBEKeySpec spec = new PBEKeySpec(password, salt, 20000000, 256);
    //PBKDF2WithHmacSHA256 is supportted from JDK1.8
    SecretKeyFactory skf = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
    byte[] hashed = skf.generateSecret(spec).getEncoded();
    return hashed;
}

```
**【错误示例】**

```
public static byte[] createHash(char[] password) throws NoSuchAlgorithmException, InvalidKeySpecException {
    SecureRandom random = SecureRandom.getInstance("SHA1PRNG");
    byte[] salt = new byte[8];
    random.nextBytes(salt);
    /* POTENTIAL FLAW: 检测口令哈希时哈希迭代值是否大于10,000,000，如果否则报告警。 */
    PBEKeySpec spec = new PBEKeySpec(password, salt, 5000, 256);
    //PBKDF2WithHmacSHA256 is supportted from JDK1.8
    SecretKeyFactory skf = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
    byte[] hashed = skf.generateSecret(spec).getEncoded();
    return hashed;
}

```
**【修复建议】**

使用一个基于密码的密钥派生函数时，迭代计数应至少为 10,000,000。这将大幅增加穷尽式密码搜索的代价，而对派生各个密钥的代价不会产生显著影响
