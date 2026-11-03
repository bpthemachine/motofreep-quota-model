# MotoFreeP attainment regression - spec S2, clustered standard errors
library(sandwich); library(lmtest)
d <- read.csv("history_core.csv")
d$tenure_min <- pmin(d$rep_tenure_months_at_start, 12)
d$enterprise <- as.integer(d$segment == "Enterprise")
d$emea <- as.integer(d$region == "EMEA"); d$apac <- as.integer(d$region == "APAC")
f <- attainment_pct ~ tenure_min + pipeline_coverage_at_start + quota_growth_pct +
     potential_to_quota_ratio + enterprise + emea + apac

m <- lm(f, data = d)                      # final fit: all four years, 160 rows
cat("\n=== S2 on FY2023-FY2026 (160 rows) ===\n"); print(summary(m))
cat("\n--- Territory-clustered standard errors ---\n")
print(coeftest(m, vcov = vcovCL(m, cluster = ~territory_id)))

# Do persistent territory differences remain? (F-test of territory effects)
m_fe <- lm(update(f, . ~ . + factor(territory_id)), data = d)
cat("\n--- Territory effects F-test ---\n"); print(anova(m, m_fe))

# Within-territory correlation of residuals year to year
r <- data.frame(t = d$territory_id, y = d$fiscal_year, e = resid(m))
w <- reshape(r, idvar = "t", timevar = "y", direction = "wide")
cat("\nResidual correlation, same territory, consecutive years:\n")
print(round(c(`23-24`=cor(w$e.2023,w$e.2024), `24-25`=cor(w$e.2024,w$e.2025), `25-26`=cor(w$e.2025,w$e.2026)),3))
write.csv(data.frame(term=names(coef(m)), coef=coef(m),
          se_ols=sqrt(diag(vcov(m))), se_cluster=sqrt(diag(vcovCL(m, cluster=~territory_id)))),
          "s2_final_coefficients.csv", row.names = FALSE)
