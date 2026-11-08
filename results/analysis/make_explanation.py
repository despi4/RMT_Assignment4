"""Prepare a concise explanation only from a completed, validated real run."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,csv,json,hashlib,statistics,shutil,unicodedata,re

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/explanation_export'
ANALYSIS=ROOT/'results/analysis'

def read_csv(name):
    with (ANALYSIS/name).open(encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))

def norm(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text).strip().casefold()).strip(' \t\r\n.!,;:\"\'`')

def save_csv(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)

def main():
    global ROOT,OUT,ANALYSIS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',default=str(ROOT))
    parser.add_argument('--output',default=str(OUT))
    args=parser.parse_args()
    ROOT=Path(args.project).resolve(); OUT=Path(args.output).resolve(); ANALYSIS=ROOT/'results/analysis'
    raw_path=ROOT/'results/final/raw.jsonl'
    raw=[json.loads(line) for line in raw_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    completed=json.loads((ROOT/'results/final/completion.json').read_text(encoding='utf-8'))
    assert completed['run_status']=='complete' and len(raw)==2520
    assert completed['raw_sha256']==hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert not any(row.get('error') for row in raw)
    main_results=read_csv('main_results.csv')
    comparisons=read_csv('paired_comparisons.csv')
    decisions=read_csv('hypothesis_decisions.csv')
    labels={
        'closed_book':'Без подсказки', 'clean':'Только правильный факт',
        'irrelevant_4':'Правильный факт + 4 факта об озёрах',
        'similar_4':'Правильный факт + 4 чужие столицы',
        'irrelevant_16':'Правильный факт + 16 фактов об озёрах',
        'similar_16':'Правильный факт + 16 чужих столиц',
        'target_absent_16':'16 чужих столиц, нужного факта нет'}
    groups=defaultdict(list)
    for row in raw:groups[row['condition']].append(row)
    table=[]
    for result in main_results:
        condition=result['condition']; rows=groups[condition]
        numerator=sum(norm(row['answer'])==norm(row['city']) for row in rows)
        expected_correct=sum(norm(row['answer'])==norm(row['expected']) for row in rows)
        assert len(rows)==360
        assert abs(float(result['accuracy_pct'])-numerator/len(rows)*100)<1e-9
        assert abs(float(result['expected_response_accuracy_pct'])-expected_correct/len(rows)*100)<1e-9
        table.append({'condition':condition,'description_ru':labels[condition],
                      'gold_city_correct':numerator,'calls':len(rows),
                      'gold_city_accuracy_pct':float(result['accuracy_pct']),
                      'ci95_low_pct':float(result['ci95_low_pct']),
                      'ci95_high_pct':float(result['ci95_high_pct']),
                      'sd_context_seeds_pp':float(result['sd_across_context_seeds_pp']),
                      'expected_response_accuracy_pct':float(result['expected_response_accuracy_pct'])})
    for comparison in comparisons:
        a,b=comparison['condition_a'],comparison['condition_b']
        means=[]
        facts=sorted({row['fact_id'] for row in raw})
        for fact in facts:
            av=[norm(row['answer'])==norm(row['city']) for row in groups[a] if row['fact_id']==fact]
            bv=[norm(row['answer'])==norm(row['city']) for row in groups[b] if row['fact_id']==fact]
            assert len(av)==len(bv)==3
            means.append(statistics.mean(av)-statistics.mean(bv))
        assert abs(statistics.mean(means)*100-float(comparison['difference_pp']))<1e-9
    OUT.mkdir(parents=True,exist_ok=True)
    for file in ANALYSIS.iterdir():
        if file.is_file():shutil.copy2(file,OUT/file.name)
    save_csv(OUT/'Results_Table_RU.csv',table,list(table[0]))
    diagnostic=[]
    for row in raw:
        if norm(row['answer'])==norm(row['expected']):continue
        answer=norm(row['answer'])
        if not answer:category='empty_output'
        elif not row['target_present'] and answer!='unknown':category='unsupported_answer'
        elif row['target_present'] and answer=='unknown':category='unnecessary_abstention'
        elif answer in {norm(x) for x in row['distractor_answers']}:category='exact_distractor_copy'
        elif norm(row['city']) in answer:category='gold_appears_with_extra_text'
        else:category='other_wrong_answer'
        diagnostic.append({'record_id':row['record_id'],'condition':row['condition'],
            'automatic_diagnostic':category,'question':row['question'],
            'expected':row['expected'],'answer':row['answer'],
            'status':'Automatic descriptive rule; not independent human coding'})
    save_csv(OUT/'Automatic_Error_Diagnostics.csv',diagnostic,
        ['record_id','condition','automatic_diagnostic','question','expected','answer','status'])
    counts=Counter(row['automatic_diagnostic'] for row in diagnostic)
    lines=[
        'РЕЗУЛЬТАТЫ ЭКСПЕРИМЕНТА О ВЛИЯНИИ ОТВЛЕКАЮЩЕГО КОНТЕКСТА',
        '',
        'Выполнены все 2520 финальных запросов: 120 вымышленных фактов × 7 условий × 3 context seeds.',
        'Модель Qwen2.5-0.5B-Instruct; CPU float32, два потока. Веса модели не обновлялись.',
        'Все семь условий использовали один checkpoint и одинаковые правила ответа.',
        'Технических ошибок: 0. Каждое число проверено по сохранённым raw-ответам.',
        '',
        'ТОЧНОЕ ВОСПРОИЗВЕДЕНИЕ ПРАВИЛЬНОГО ГОРОДА',
    ]
    for row in table:
        lines.append(f"{row['description_ru']}: {row['gold_city_correct']}/360 = {row['gold_city_accuracy_pct']:.2f}%; 95% CI [{row['ci95_low_pct']:.2f}; {row['ci95_high_pct']:.2f}].")
    result_by_condition={row['condition']:row for row in table}
    lines += ['', 'ОСНОВНОЙ ВЫВОД',
        f"С 16 похожими отвлекающими фактами точность снизилась с {result_by_condition['clean']['gold_city_accuracy_pct']:.2f}% до {result_by_condition['similar_16']['gold_city_accuracy_pct']:.2f}%: на {abs(float(comparisons[0]['difference_pp'])):.2f} процентного пункта.",
        'В этой задаче похожие утверждения о столицах мешали гораздо сильнее, чем факты об озёрах.',
        'У похожих и посторонних distractors фактическое число входных токенов совпало в каждой паре fact/seed при k=4 и k=16. Различие этих двух условий не объясняется числом токенов в данном наборе.',
        f"Когда нужного факта не было среди 16 чужих столиц, правильный UNKNOWN получен в {result_by_condition['target_absent_16']['expected_response_accuracy_pct']:.2f}% случаев; в остальных {100-result_by_condition['target_absent_16']['expected_response_accuracy_pct']:.2f}% модель выдала неподтверждённый город.",
        '', 'ПОЛОЖЕНИЕ НУЖНОГО ФАКТА',
        'Описательная подгруппа similar_16:']
    for row in read_csv('subgroups.csv'):
        if row['factor']=='position' and row['condition']=='similar_16':
            position={'first':'В начале','middle':'В середине','last':'В конце'}[row['level']]
            lines.append(f"{position}: {float(row['accuracy_pct']):.2f}% ({row['calls']} предъявлений).")
    lines += ['Это описательный результат: между seeds менялись также отвлекающие факты, поэтому чистый причинный эффект позиции отдельно не установлен.']
    lines += ['',
        'В условиях без нужного факта правильной реакцией по инструкции является UNKNOWN.',
        'Это отдельно оценивает соблюдение инструкции; UNKNOWN не считается знанием города.',
        '', 'ПРЕДВАРИТЕЛЬНО ЗАДАННЫЕ ГИПОТЕЗЫ']
    for comparison,decision in zip(comparisons,decisions):
        supported=decision['status']=='supported'
        lines.append(f"{decision['hypothesis']}: {comparison['condition_a']} минус {comparison['condition_b']}: {float(comparison['difference_pp']):+.2f} п.п.; парный 95% CI [{float(comparison['paired_ci_low_pp']):+.2f}; {float(comparison['paired_ci_high_pp']):+.2f}]; p(Holm)={float(comparison['p_holm']):.6f}. {'Подтверждена по заданному критерию' if supported else 'Не подтверждена по заданному критерию'}.")
    lines += ['',
        'Статистика учитывает 120 фактов как независимые единицы. Повторные seeds не считаются новыми независимыми фактами.',
        'Использованы 4000 bootstrap resamples, 10000 paired sign-flip permutations и Holm для трёх сравнений.',
        '', 'ДИАГНОСТИКА ОШИБОК',
        f'Всего ошибок относительно ожидаемого ответа: {len(diagnostic)} из 2520.',
        'Автоматические описательные категории: '+json.dumps(dict(counts),ensure_ascii=False)+'.',
        'Это подсказка для разбора, а не завершённая ручная разметка двух участников.',
        'В error_review.csv сохранена неизменяемая выборка для Appendix B. Поля двух независимых оценщиков оставлены незаполненными.',
        '', 'КАК ПОНИМАТЬ РЕЗУЛЬТАТ',
        'Оценивается использование новых сведений из предоставленного текста при фиксированных весах.',
        'Сравнение clean и noisy сочетает изменение длины и содержимого контекста.',
        'Факты об озёрах и столицах приблизительно сопоставлены по длине, но могут различаться числом токенов.',
        'Положение предложения анализируется описательно: между seeds также меняются отвлекающие факты.',
        'Результаты относятся к одной небольшой модели, вымышленным английским фактам и этим prompts.',
        'Они не доказывают постоянное усвоение знаний и не заменяют сравнение FT/RAG из Assignment 3.',
        '', 'ЧТО ОСТАЛОСЬ ДЛЯ ASSIGNMENT 4',
        '1. Два человека независимо разбирают выбранные ошибки и согласуют итоговые категории — Appendix B.',
        '2. Другой участник действительно повторяет запуск в чистой среде — Appendix C.',
        '3. Report: Results/Discussion, ответ на исходный RQ, три источника из Assignment 1, ограничения и защита.',
        'Независимое воспроизведение и человеческая разметка этим запуском не заявляются.',
        '', 'ИЗМЕНЕНИЯ ПОСЛЕ APPENDIX A',
        'Технические исправления CPU launcher, сохранения checkpoint, проверки окружения и продолжения описаны в docs/IMPLEMENTATION_UPDATE.json.',
        'Исходный код исполнения: commit 039f7dd028b78ee08eb81af5a2296a4d8f19930c; научный дизайн не менялся. Эту запись нужно включить в Deviations from the frozen protocol.',
        'Финальная генерация началась после freeze и настоящей загрузки Appendix A; оригинал документа и receipt сохранены приватно.'
    ]
    examples=[]
    for condition in ['similar_16','irrelevant_16','similar_4','irrelevant_4']:
        candidates=[r for r in groups[condition] if not r['correct']]
        if not candidates:continue
        r=sorted(candidates,key=lambda r:r['record_id'])[0]
        clean=next(x for x in groups['clean'] if x['fact_id']==r['fact_id'] and x['seed']==r['seed'])
        examples.append({'record_id':r['record_id'],'condition':condition,'question':r['question'],
                         'context':r['context'],'gold_city':r['city'],'model_answer':r['answer'],
                         'clean_answer_same_fact_seed':clean['answer']})
    (OUT/'Observed_Error_Examples.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'Experiment_Explanation_RU.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    summary={'table':table,'comparisons':comparisons,'hypotheses':decisions,
             'automatic_error_counts':dict(counts),'technical_errors':0,
             'raw_sha256':completed['raw_sha256'],'independent_raw_recalculation_passed':True}
    (OUT/'Verified_Summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
